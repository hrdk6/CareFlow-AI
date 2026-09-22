"""Recording observations and the ward board.

The score is NEWS2 (app.services.news2) and the escalation rules are the hospital's own: the Patient Safety
Guidelines' rapid-response criteria and the Emergency Admission Procedure's early-warning thresholds. Both are
deterministic, and each row on the board cites the policy section it applies. How often a patient is due their
next set of observations follows the score itself, so "overdue" is the chart's rule, not an invention.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.access import AccessPolicy
from app.llm.evidence import EvidenceStore
from app.models import Admission, Patient, User, VitalSigns
from app.schemas.vitals import News2Out, TrendPoint, VitalSignsIn, VitalSignsOut, WardBoardOut, WardPatient
from app.services.events import hub
from app.services.news2 import NOT_FOR_CHILDREN, Observations, applies_to, rapid_response_triggers, score
from app.services.policy_refs import indexed_document, section_citations

SAFETY_POLICY_KEY = "cf-saf-01"
EMERGENCY_PROCEDURE_KEY = "cf-proc-em-03"
BOARD_NOTE = ("NEWS2 (Royal College of Physicians, 2017) is a track-and-trigger score, not a prediction: the seven "
              "observations are banded and added up. Escalation follows the hospital's own policies, cited below.")
TREND_POINTS = 12


def age_of(patient: Patient, on: datetime | None = None) -> int:
    today = (on or datetime.now(UTC)).date()
    dob = patient.date_of_birth
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def observations_of(v: VitalSigns) -> Observations:
    return Observations(respiratory_rate=v.respiratory_rate, spo2=v.spo2, on_oxygen=v.on_oxygen,
                        systolic_bp=v.systolic_bp, heart_rate=v.heart_rate, consciousness=v.consciousness,
                        temperature=v.temperature, spo2_scale=v.spo2_scale)


def news2_out(current: Observations, previous: Observations | None = None, age: int | None = None) -> News2Out:
    """The score, and what the hospital asks to happen about it. For a patient the chart is not validated for
    (a child), the values are still recorded but the risk band is withheld rather than implied."""
    n = score(current)
    applies = applies_to(age)
    return News2Out(score=n.score, risk=n.risk, label=n.label, parameters=n.parameters,
                    single_parameter_3=n.single_parameter_3, due_within_hours=n.due_within_hours,
                    response=n.response if applies else "Follow the hospital's paediatric early warning chart.",
                    monitoring=n.monitoring if applies else "As the paediatric chart requires",
                    triggers=rapid_response_triggers(current, n, previous) if applies else [],
                    applies=applies, note=None if applies else NOT_FOR_CHILDREN)


def vitals_out(v: VitalSigns, previous: VitalSigns | None = None, age: int | None = None) -> VitalSignsOut:
    columns = {c: getattr(v, c) for c in VitalSignsOut.model_fields if c not in ("recorded_by", "news2")}
    return VitalSignsOut(**columns, recorded_by=v.recorded_by.full_name if v.recorded_by else None,
                         news2=news2_out(observations_of(v), observations_of(previous) if previous else None, age))


def previous_before(db: Session, patient_id: int, moment: datetime) -> VitalSigns | None:
    return db.scalar(select(VitalSigns).where(VitalSigns.patient_id == patient_id, VitalSigns.recorded_at < moment)
                     .order_by(VitalSigns.recorded_at.desc()).limit(1))


def record(db: Session, user: User, patient: Patient, body: VitalSignsIn) -> VitalSignsOut:
    """Save one set of observations against the patient's current admission (if any) and tell open streams."""
    recorded_at = body.recorded_at or datetime.now(UTC)
    admission = db.scalar(select(Admission).where(Admission.patient_id == patient.id, Admission.status == "admitted"))
    o = Observations(respiratory_rate=body.respiratory_rate, spo2=body.spo2, on_oxygen=body.on_oxygen,
                     systolic_bp=body.systolic_bp, heart_rate=body.heart_rate, consciousness=body.consciousness,
                     temperature=body.temperature, spo2_scale=body.spo2_scale)
    n = score(o)
    row = VitalSigns(patient_id=patient.id, admission_id=admission.id if admission else None, recorded_at=recorded_at,
                     recorded_by_user_id=user.id, news2_score=n.score, news2_risk=n.risk, source="manual",
                     **body.model_dump(exclude={"recorded_at"}))
    db.add(row)
    db.flush()
    db.refresh(row)
    out = vitals_out(row, previous_before(db, patient.id, recorded_at), age_of(patient))
    audit("vitals.record", user=user, resource_type="vital_signs", resource_id=row.id, patient_id=patient.id,
          details={"news2": n.score, "risk": n.risk, "triggers": len(out.news2.triggers)})
    # Ids and the score only: a stream never carries a name or a value.
    hub.publish({"type": "observation", "patient_id": patient.id, "admission_id": row.admission_id,
                 "news2": n.score, "risk": n.risk, "triggers": len(out.news2.triggers),
                 "recorded_at": recorded_at.isoformat()})
    return out


def history(db: Session, patient: Patient, *, hours: int = 72, limit: int = 200) -> list[VitalSignsOut]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = db.scalars(select(VitalSigns).where(VitalSigns.patient_id == patient.id, VitalSigns.recorded_at >= since)
                      .order_by(VitalSigns.recorded_at.desc()).limit(limit)).all()
    # Each set is scored against the one before it, so "new confusion" is recognised as new.
    return [vitals_out(v, rows[i + 1] if i + 1 < len(rows) else None, age_of(patient)) for i, v in enumerate(rows)]


def recent_observations(db: Session, patient_ids: list[int]) -> dict[int, list[VitalSigns]]:
    """The last few sets for each patient, newest first, in one query rather than one query per bed."""
    if not patient_ids:
        return {}
    ranked = select(VitalSigns, func.row_number().over(
        partition_by=VitalSigns.patient_id, order_by=VitalSigns.recorded_at.desc()).label("rank")).where(
        VitalSigns.patient_id.in_(patient_ids)).subquery()
    rows = db.scalars(select(VitalSigns).from_statement(
        select(ranked).where(ranked.c.rank <= TREND_POINTS).order_by(ranked.c.patient_id, ranked.c.recorded_at.desc())
    )).unique().all()
    out: dict[int, list[VitalSigns]] = {}
    for row in rows:
        out.setdefault(row.patient_id, []).append(row)
    return out


def board(db: Session, policy: AccessPolicy) -> WardBoardOut:
    """Every inpatient the caller may see, worst first, with what the policy says to do about them."""
    now = datetime.now(UTC)
    admissions = db.scalars(select(Admission).where(Admission.status == "admitted",
                                                    Admission.patient_id.in_(policy.clinical_patient_ids()))).all()
    patient_ids = [a.patient_id for a in admissions]
    patients = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_(patient_ids)))} if admissions else {}
    observations = recent_observations(db, patient_ids)
    rows: list[WardPatient] = []
    counts = {"inpatients": len(admissions), "low": 0, "low_medium": 0, "medium": 0, "high": 0, "overdue": 0,
              "rapid_response": 0, "no_observations": 0, "not_scored": 0}
    for adm in admissions:
        patient = patients[adm.patient_id]
        recent = observations.get(patient.id, [])
        age = age_of(patient, now)
        latest = vitals_out(recent[0], recent[1] if len(recent) > 1 else None, age) if recent else None
        due_at = overdue = None
        if latest and not latest.news2.applies:
            counts["not_scored"] += 1  # a child: the adult chart's bands and frequencies do not apply
        elif latest:
            counts[latest.news2.risk] += 1
            due_at = latest.recorded_at + timedelta(hours=latest.news2.due_within_hours)
            if due_at < now:
                overdue = round((now - due_at).total_seconds() / 3600, 1)
                counts["overdue"] += 1
            if latest.news2.triggers:
                counts["rapid_response"] += 1
        else:
            counts["no_observations"] += 1
        rows.append(WardPatient(
            patient_id=patient.id, mrn=patient.mrn, full_name=patient.full_name, sex=patient.sex, age=age,
            department=adm.department.name, ward=adm.ward, admitted_at=adm.admitted_at,
            day_of_stay=(now.date() - adm.admitted_at.date()).days + 1, reason=adm.reason,
            attending=adm.attending_doctor.full_name if adm.attending_doctor else None, latest=latest,
            trend=[TrendPoint(at=v.recorded_at, score=v.news2_score) for v in reversed(recent)],
            due_at=due_at, overdue_hours=overdue))
    # Worst first; a patient the chart does not apply to is not ranked by a score that does not mean anything.
    rows.sort(key=lambda r: (-(r.latest.news2.score if r.latest and r.latest.news2.applies else -1),
                             -(r.overdue_hours or 0), r.full_name))

    ev = EvidenceStore()
    for key, sections in ((SAFETY_POLICY_KEY, {"deterioration": "recognising deterioration"}),
                          (EMERGENCY_PROCEDURE_KEY, {"early_warning": "early warning score"})):
        doc = indexed_document(db, policy, key)
        if doc is not None:
            section_citations(db, ev, doc, sections)
    return WardBoardOut(generated_at=now, patients=rows, counts=counts,
                        citations=[ev.citation(sid) for sid in ev.sources], note=BOARD_NOTE)
