"""Online feature engineering: hospital database -> model feature contract.

The readmission model is defined relative to an inpatient stay; we score the patient's current
admission (with data available so far) or, if not admitted, their most recent discharge.
Look-back windows ("prior year") are anchored at the admission time, exactly like the training data.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Admission, Appointment, Department, Diagnosis, LabReport, Medication, Patient, Prescription
from app.seed.catalog import DIABETES_CLASSES

SPECIALTY_BY_DEPARTMENT = {
    "GM": "general_medicine", "CARD": "cardiology", "NEUR": "neurology", "ORTH": "orthopedics",
    "PED": "pediatrics", "DERM": "dermatology", "EM": "emergency",
}


@dataclass
class FeatureBuild:
    features: dict
    admission: Admission
    notes: list[str] = field(default_factory=list)
    in_training_population: bool = True


def reference_admission(db: Session, patient_id: int) -> Admission | None:
    current = db.scalar(select(Admission).where(Admission.patient_id == patient_id, Admission.status == "admitted")
                        .order_by(Admission.admitted_at.desc()))
    if current is not None:
        return current
    return db.scalar(select(Admission).where(Admission.patient_id == patient_id)
                     .order_by(Admission.admitted_at.desc()).limit(1))


def _prior_year_counts(db: Session, patient_id: int, adm: Admission) -> dict:
    start = adm.admitted_at - timedelta(days=365)
    visits = dict(db.execute(
        select(Appointment.appointment_type, func.count())
        .where(Appointment.patient_id == patient_id, Appointment.status == "completed",
               Appointment.scheduled_start >= start, Appointment.scheduled_start < adm.admitted_at)
        .group_by(Appointment.appointment_type)).all())
    inpatient = db.scalar(select(func.count()).select_from(Admission).where(
        Admission.patient_id == patient_id, Admission.id != adm.id,
        Admission.admitted_at >= start, Admission.admitted_at < adm.admitted_at)) or 0
    return {
        "number_outpatient": visits.get("outpatient", 0) + visits.get("follow_up", 0) + visits.get("telehealth", 0),
        "number_emergency": visits.get("emergency", 0),
        "number_inpatient": inpatient,
    }


def _common(db: Session, patient: Patient, adm: Admission) -> tuple[dict, list[str]]:
    notes: list[str] = []
    age = (adm.admitted_at.date() - patient.date_of_birth).days / 365.25
    dept_code = db.scalar(select(Department.code).where(Department.id == adm.department_id))
    primary = db.scalar(select(Diagnosis.category).where(Diagnosis.admission_id == adm.id, Diagnosis.is_primary))
    if primary is None:
        notes.append("No primary diagnosis coded for the admission; using 'other'.")
    feats = {
        "age_years": round(age, 1),
        "gender": patient.sex if patient.sex in ("F", "M") else None,
        "admission_type": adm.admission_type,
        "admission_source": adm.admission_source,
        "admitting_specialty": SPECIALTY_BY_DEPARTMENT.get(dept_code, "other"),
        "primary_diagnosis_category": primary or "other",
        **_prior_year_counts(db, patient.id, adm),
    }
    return feats, notes


def _is_diabetic(db: Session, patient_id: int) -> bool:
    return bool(db.scalar(select(func.count()).select_from(Diagnosis).where(
        Diagnosis.patient_id == patient_id, Diagnosis.category == "diabetes")))


def readmission_features(db: Session, patient: Patient, adm: Admission) -> FeatureBuild:
    feats, notes = _common(db, patient, adm)
    end = adm.discharged_at or func.now()
    if adm.discharged_at is None:
        los_days = max(1, (adm.admitted_at.now(adm.admitted_at.tzinfo) - adm.admitted_at).days)
        notes.append("Patient is still admitted: stay length, labs, medications and discharge destination are "
                     "provisional, while the model was trained on completed stays.")
    else:
        los_days = max(1, round((adm.discharged_at - adm.admitted_at).total_seconds() / 86400))

    labs = db.execute(select(LabReport.test_code, LabReport.value).where(LabReport.admission_id == adm.id)).all()
    a1c = [v for code, v in labs if code == "HBA1C" and v is not None]
    glucose = [v for code, v in labs if code == "GLU" and v is not None]

    rx = db.execute(
        select(Medication.drug_class, Prescription.change_reason, Prescription.medication_id)
        .join(Medication, Medication.id == Prescription.medication_id)
        .where(Prescription.patient_id == patient.id,
               (Prescription.admission_id == adm.id)
               | ((Prescription.admission_id.is_(None)) & (Prescription.start_date >= adm.admitted_at.date())
                  & (Prescription.start_date <= func.date(end))))).all()
    diabetes_rx = [(cls, reason) for cls, reason, _ in rx if cls in DIABETES_CLASSES]
    insulin_reasons = [(reason or "").lower() for cls, reason in diabetes_rx if cls == "insulin"]
    if not insulin_reasons:
        insulin = "none"
    elif any("increase" in r for r in insulin_reasons):
        insulin = "up"
    elif any("reduce" in r or "decrease" in r for r in insulin_reasons):
        insulin = "down"
    else:
        insulin = "steady"
    active_diabetes_outpatient = db.scalar(select(func.count()).select_from(Prescription)
                                           .join(Medication, Medication.id == Prescription.medication_id)
                                           .where(Prescription.patient_id == patient.id,
                                                  Prescription.status == "active",
                                                  Medication.drug_class.in_(DIABETES_CLASSES))) or 0
    n_meds = db.scalar(select(func.count(distinct(Prescription.medication_id)))
                       .where(Prescription.admission_id == adm.id)) or 0
    n_dx = db.scalar(select(func.count(distinct(Diagnosis.icd10_code))).where(
        Diagnosis.patient_id == patient.id,
        (Diagnosis.admission_id == adm.id)
        | (Diagnosis.is_chronic & (Diagnosis.diagnosed_on <= adm.admitted_at.date())))) or 0

    feats.update({
        "time_in_hospital": float(min(los_days, 60)),
        "num_lab_procedures": float(len(labs)),
        "num_medications": float(n_meds),
        "number_diagnoses": float(min(n_dx, 16)),
        "discharge_disposition": adm.discharge_disposition if adm.discharge_disposition not in (None, "expired")
        else "unknown",
        "a1c_result": "none" if not a1c else ("high_8" if max(a1c) > 8 else "high_7" if max(a1c) > 7 else "normal"),
        "max_glucose": "none" if not glucose else (
            "high_300" if max(glucose) > 300 else "high_200" if max(glucose) > 200 else "normal"),
        "insulin_regimen": insulin,
        "medication_changed": float(any(reason for _, reason in diabetes_rx)),
        "on_diabetes_medication": float(bool(diabetes_rx) or active_diabetes_outpatient > 0),
    })
    diabetic = _is_diabetic(db, patient.id)
    if not diabetic:
        notes.append("Patient has no diabetes diagnosis; the model was trained only on diabetic inpatients, "
                     "so this estimate is outside its training population.")
    return FeatureBuild(feats, adm, notes, diabetic)


def los_features(db: Session, patient: Patient, adm: Admission) -> FeatureBuild:
    feats, notes = _common(db, patient, adm)
    diabetic = _is_diabetic(db, patient.id)
    if not diabetic:
        notes.append("Patient has no diabetes diagnosis; the model was trained only on diabetic inpatients.")
    return FeatureBuild(feats, adm, notes, diabetic)
