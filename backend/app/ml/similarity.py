"""Patient similarity over a structured clinical representation.

Representation (32 dims, version "sim-v1"):
  8  numeric  z-scores against FIXED reference scales (not dataset statistics, so a vector never
             changes because other patients were added), clipped to +-3, weight 0.5
  9  diagnosis-category multi-hot (chronic/active or diagnosed in the last 2 years), weight 1.0
  12 medication-group multi-hot (active outpatient prescriptions), weight 0.6
  2  sex one-hot, weight 0.3
  1  pediatric flag (age < 18), weight 1.5 - children should essentially never match adults
Block weights encode the judgement that shared problems matter most, current treatment next,
demographics least. Metric: cosine distance, served by pgvector (HNSW index, `<=>`).

Authorization: candidate patients are restricted IN SQL to those the requesting user may access
(AccessPolicy.clinical_patient_ids) before ranking. Similar != same diagnosis, treatment or outcome.
"""
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Admission, Appointment, Diagnosis, LabReport, Medication, Patient, PatientEmbedding, Prescription
from app.models.clinical import DIAGNOSIS_CATEGORIES
from app.models.ml import SIMILARITY_DIM

REPRESENTATION_VERSION = "sim-v1"

NUMERIC_SCALES = {  # feature: (reference mean, reference sd)
    "age": (55, 20), "admissions_2y": (1.0, 1.5), "ed_visits_2y": (0.5, 1.0), "mean_los_days": (4.0, 3.0),
    "active_medications": (5.0, 3.0), "chronic_conditions": (2.5, 1.5), "last_hba1c": (7.5, 1.2),
    "last_egfr": (75, 20),
}
MED_GROUPS = {
    "oral_antidiabetic": {"biguanide", "sulfonylurea", "dpp4_inhibitor", "sglt2_inhibitor"},
    "insulin": {"insulin"}, "glp1_agonist": {"glp1_agonist"},
    "renin_angiotensin": {"ace_inhibitor", "arb"}, "other_antihypertensive": {"calcium_channel_blocker", "thiazide"},
    "beta_blocker": {"beta_blocker"}, "diuretic": {"loop_diuretic", "mra"}, "statin": {"statin"},
    "antithrombotic": {"antiplatelet", "anticoagulant"},
    "respiratory": {"bronchodilator", "inhaled_corticosteroid", "corticosteroid"},
    "neuro_psych": {"anticonvulsant", "triptan", "gabapentinoid", "ssri"},
    "dermatologic": {"topical_corticosteroid", "topical_vitamin_d"},
}
WEIGHTS = {"numeric": 0.5, "diagnosis": 1.0, "medication": 0.6, "sex": 0.3, "pediatric": 1.5}

FEATURE_NAMES = (
    [f"num:{k}" for k in NUMERIC_SCALES] + [f"dx:{c}" for c in DIAGNOSIS_CATEGORIES]
    + [f"rx:{g}" for g in MED_GROUPS] + ["sex:F", "sex:M", "pediatric"]
)
assert len(FEATURE_NAMES) == SIMILARITY_DIM, "update SIMILARITY_DIM + migration when the representation changes"


def patient_profiles(db: Session, patient_ids: list[int] | None = None, today: date | None = None) -> dict[int, dict]:
    """Raw, human-readable profile per patient (bulk SQL - one query per table)."""
    today = today or datetime.now(UTC).date()
    since = datetime.combine(today - timedelta(days=730), datetime.min.time(), tzinfo=UTC)

    def scoped(stmt, col):
        return stmt.where(col.in_(patient_ids)) if patient_ids is not None else stmt

    profiles: dict[int, dict] = {}
    for pid, dob, sex in db.execute(scoped(select(Patient.id, Patient.date_of_birth, Patient.sex), Patient.id)):
        profiles[pid] = {"age": round((today - dob).days / 365.25, 1), "sex": sex, "admissions_2y": 0,
                         "ed_visits_2y": 0, "mean_los_days": None, "active_medications": 0, "chronic_conditions": 0,
                         "last_hba1c": None, "last_egfr": None, "diagnosis_categories": set(),
                         "medication_groups": set(), "diagnoses": set()}
    adm_stmt = select(Admission.patient_id, func.count(),
                      func.avg(func.extract("epoch", Admission.discharged_at - Admission.admitted_at) / 86400)
                      ).where(Admission.admitted_at >= since).group_by(Admission.patient_id)
    for pid, n, los in db.execute(scoped(adm_stmt, Admission.patient_id)):
        profiles[pid]["admissions_2y"] = n
        profiles[pid]["mean_los_days"] = round(float(los), 1) if los is not None else None
    ed_stmt = select(Appointment.patient_id, func.count()).where(
        Appointment.appointment_type == "emergency", Appointment.status == "completed",
        Appointment.scheduled_start >= since).group_by(Appointment.patient_id)
    for pid, n in db.execute(scoped(ed_stmt, Appointment.patient_id)):
        profiles[pid]["ed_visits_2y"] = n
    rx_stmt = select(Prescription.patient_id, Medication.drug_class).join(Medication).where(
        Prescription.status == "active", Prescription.admission_id.is_(None))
    for pid, cls in db.execute(scoped(rx_stmt, Prescription.patient_id)):
        p = profiles[pid]
        p["active_medications"] += 1
        for group, classes in MED_GROUPS.items():
            if cls in classes:
                p["medication_groups"].add(group)
    dx_stmt = select(Diagnosis.patient_id, Diagnosis.category, Diagnosis.is_chronic, Diagnosis.status,
                     Diagnosis.diagnosed_on, Diagnosis.description)
    for pid, cat, chronic, status, on, desc in db.execute(scoped(dx_stmt, Diagnosis.patient_id)):
        p = profiles[pid]
        if (chronic and status == "active") or on >= since.date():
            p["diagnosis_categories"].add(cat)
            p["diagnoses"].add(desc)
        if chronic and status == "active":
            p["chronic_conditions"] += 1
    lab_stmt = (select(LabReport.patient_id, LabReport.test_code, LabReport.value)
                .where(LabReport.test_code.in_(["HBA1C", "EGFR"]))
                .distinct(LabReport.patient_id, LabReport.test_code)
                .order_by(LabReport.patient_id, LabReport.test_code, LabReport.collected_at.desc()))
    for pid, code, value in db.execute(scoped(lab_stmt, LabReport.patient_id)):
        profiles[pid]["last_hba1c" if code == "HBA1C" else "last_egfr"] = value
    return profiles


def vectorize(profile: dict) -> list[float]:
    vec: list[float] = []
    for name, (mean, sd) in NUMERIC_SCALES.items():
        value = profile.get(name)
        z = 0.0 if value is None else max(-3.0, min(3.0, (float(value) - mean) / sd))  # missing -> reference mean
        vec.append(z * WEIGHTS["numeric"])
    vec += [WEIGHTS["diagnosis"] * float(c in profile["diagnosis_categories"]) for c in DIAGNOSIS_CATEGORIES]
    vec += [WEIGHTS["medication"] * float(g in profile["medication_groups"]) for g in MED_GROUPS]
    vec += [WEIGHTS["sex"] * float(profile["sex"] == "F"), WEIGHTS["sex"] * float(profile["sex"] == "M")]
    vec.append(WEIGHTS["pediatric"] * float(profile["age"] < 18))
    return vec


def _json_profile(profile: dict) -> dict:
    return {k: sorted(v) if isinstance(v, set) else v for k, v in profile.items()}


def upsert_representations(db: Session, profiles: dict[int, dict]) -> int:
    for pid, profile in profiles.items():
        stmt = insert(PatientEmbedding).values(
            patient_id=pid, representation_version=REPRESENTATION_VERSION, vector=vectorize(profile),
            features=_json_profile(profile), updated_at=func.now())
        db.execute(stmt.on_conflict_do_update(index_elements=[PatientEmbedding.patient_id], set_={
            "representation_version": stmt.excluded.representation_version, "vector": stmt.excluded.vector,
            "features": stmt.excluded.features, "updated_at": func.now()}))
    return len(profiles)


def rebuild_all_representations(db: Session) -> int:
    return upsert_representations(db, patient_profiles(db))


def find_similar(db: Session, patient_id: int, allowed_ids_subquery, k: int = 5) -> tuple[dict, list[dict]]:
    """Return (query profile, neighbours). Refreshes the query patient's vector first."""
    profiles = patient_profiles(db, [patient_id])
    upsert_representations(db, profiles)
    query = profiles[patient_id]
    qvec = vectorize(query)
    db.execute(text("SET LOCAL hnsw.ef_search = 200"))  # widen the candidate pool before filtering
    distance = PatientEmbedding.vector.cosine_distance(qvec)
    rows = db.execute(
        select(PatientEmbedding.patient_id, PatientEmbedding.features, distance.label("distance"))
        .where(and_(PatientEmbedding.patient_id != patient_id, PatientEmbedding.patient_id.in_(allowed_ids_subquery)))
        .order_by(distance).limit(k)).all()
    neighbours = []
    for pid, features, dist in rows:
        shared_dx = sorted(set(query["diagnosis_categories"]) & set(features["diagnosis_categories"]))
        shared_rx = sorted(set(query["medication_groups"]) & set(features["medication_groups"]))
        neighbours.append({"patient_id": pid, "similarity": round(1 - float(dist), 4), "profile": features,
                           "shared_diagnosis_categories": shared_dx, "shared_medication_groups": shared_rx})
    return _json_profile(query), neighbours


def cohort_patterns(db: Session, neighbour_ids: list[int]) -> dict:
    """Aggregate historical patterns across neighbours (outcomes are descriptive, not predictive)."""
    if not neighbour_ids:
        return {}
    admissions = db.execute(select(Admission.patient_id, Admission.admitted_at, Admission.discharged_at)
                            .where(Admission.patient_id.in_(neighbour_ids)).order_by(Admission.admitted_at)).all()
    by_patient: dict[int, list] = defaultdict(list)
    for pid, a, d in admissions:
        by_patient[pid].append((a, d))
    readmit = 0
    discharges = 0
    stays = []
    for stays_p in by_patient.values():
        for i, (a, d) in enumerate(stays_p):
            if d is None:
                continue
            discharges += 1
            stays.append((d - a).total_seconds() / 86400)
            if i + 1 < len(stays_p) and (stays_p[i + 1][0] - d).days <= 30:
                readmit += 1
    dx = db.execute(select(Diagnosis.description, func.count(func.distinct(Diagnosis.patient_id)))
                    .where(Diagnosis.patient_id.in_(neighbour_ids)).group_by(Diagnosis.description)
                    .order_by(func.count(func.distinct(Diagnosis.patient_id)).desc()).limit(6)).all()
    meds = db.execute(select(Medication.name, func.count(func.distinct(Prescription.patient_id)))
                      .join(Medication).where(Prescription.patient_id.in_(neighbour_ids),
                                              Prescription.status == "active", Prescription.admission_id.is_(None))
                      .group_by(Medication.name).order_by(func.count(func.distinct(Prescription.patient_id)).desc())
                      .limit(6)).all()
    return {
        "cohort_size": len(neighbour_ids),
        "patients_with_admissions": len(by_patient),
        "discharges": discharges,
        "readmissions_within_30d": readmit,
        "readmission_rate": round(readmit / discharges, 3) if discharges else None,
        "mean_length_of_stay_days": round(sum(stays) / len(stays), 1) if stays else None,
        "common_diagnoses": [{"description": d, "patients": n} for d, n in dx],
        "common_active_medications": [{"medication": m, "patients": n} for m, n in meds],
    }
