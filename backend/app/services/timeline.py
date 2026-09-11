"""Chronological patient timeline assembled from structured records (no LLM involved).

Every event links back to its source row (source_type, source_id) so AI summaries built on the
timeline can cite the underlying record.
"""
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Admission, Appointment, Diagnosis, LabReport, MedicalRecord, Medication, Prescription
from app.schemas.clinical import TimelineEvent

_DISPOSITION = {"home": "home", "home_health": "home with home health", "skilled_nursing": "a skilled nursing facility",
                "rehab": "rehabilitation", "transfer": "another facility", "ama": "against medical advice",
                "expired": "deceased"}


def _at(d: date) -> datetime:
    return datetime.combine(d, time(12, 0), tzinfo=UTC)


def build_timeline(db: Session, patient_id: int, *, since: date | None = None,
                   categories: set[str] | None = None) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    since_dt = _at(since) if since else None

    for a in db.scalars(select(Admission).where(Admission.patient_id == patient_id)):
        events.append(TimelineEvent(
            id=f"admission:{a.id}", at=a.admitted_at, category="admission",
            title=f"Admitted to {a.department.name}: {a.reason}",
            detail=f"{a.admission_type.title()} admission via {a.admission_source.replace('_', ' ')}"
                   + (f", attending {a.attending_doctor.full_name}" if a.attending_doctor else ""),
            source_type="admission", source_id=a.id,
            severity="warning" if a.admission_type == "emergency" else "info"))
        if a.discharged_at:
            events.append(TimelineEvent(
                id=f"discharge:{a.id}", at=a.discharged_at, category="discharge",
                title=f"Discharged to {_DISPOSITION.get(a.discharge_disposition or '', 'unknown')} "
                      f"after {a.length_of_stay_days} days",
                source_type="admission", source_id=a.id))

    for r in db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == patient_id)):
        category = "emergency" if r.record_type == "emergency" else "visit"
        title = {"discharge_summary": "Discharge summary", "follow_up": "Follow-up visit",
                 "consultation": "Consultation", "progress_note": "Progress note",
                 "emergency": "Emergency assessment"}[r.record_type]
        events.append(TimelineEvent(
            id=f"record:{r.id}", at=_at(r.visit_date), category=category,
            title=f"{title}: {r.chief_complaint}", detail=r.treatment_plan or r.diagnosis_summary,
            source_type="medical_record", source_id=r.id, severity="warning" if category == "emergency" else "info"))

    for dx in db.scalars(select(Diagnosis).where(Diagnosis.patient_id == patient_id,
                                                 Diagnosis.is_chronic | Diagnosis.is_primary)):
        if dx.admission_id is not None and not dx.is_chronic:
            continue  # acute admission diagnoses already appear on the admission event
        events.append(TimelineEvent(
            id=f"diagnosis:{dx.id}", at=_at(dx.diagnosed_on), category="diagnosis",
            title=f"Diagnosed: {dx.description} ({dx.icd10_code})", source_type="diagnosis", source_id=dx.id))

    rx_rows = db.execute(select(Prescription, Medication.name).join(Medication)
                         .where(Prescription.patient_id == patient_id, Prescription.admission_id.is_(None))).all()
    for rx, med in rx_rows:
        reason = rx.change_reason or ""
        if rx.status == "discontinued" and reason.lower().startswith("stopped"):
            events.append(TimelineEvent(
                id=f"rx-stop:{rx.id}", at=_at(rx.end_date or rx.start_date), category="medication_stop",
                title=f"Stopped {med}", detail=reason, source_type="prescription", source_id=rx.id,
                severity="warning"))
            continue
        category = "medication_change" if reason.lower().startswith(("dose", "inpatient dose")) else "medication_start"
        events.append(TimelineEvent(
            id=f"rx:{rx.id}", at=_at(rx.start_date), category=category,
            title=f"{'Changed' if category == 'medication_change' else 'Started'} {med} {rx.dosage} {rx.frequency}",
            detail=reason or None, source_type="prescription", source_id=rx.id))

    labs = db.scalars(select(LabReport).where(LabReport.patient_id == patient_id, LabReport.flag != "normal"))
    for lab in labs:
        # Outpatient abnormal results, plus critical inpatient values (routine inpatient panels would flood it).
        if lab.admission_id is not None and lab.flag != "critical" and lab.test_code != "HBA1C":
            continue
        events.append(TimelineEvent(
            id=f"lab:{lab.id}", at=lab.collected_at, category="lab_abnormal",
            title=f"{lab.test_name} {lab.value:g} {lab.unit or ''} ({lab.flag})".replace("  ", " "),
            source_type="lab_report", source_id=lab.id,
            severity="critical" if lab.flag == "critical" else "warning"))

    now = datetime.now(UTC)
    for appt in db.scalars(select(Appointment).where(Appointment.patient_id == patient_id,
                                                     Appointment.scheduled_start >= now,
                                                     Appointment.status.in_(["scheduled", "checked_in"]))):
        events.append(TimelineEvent(
            id=f"appointment:{appt.id}", at=appt.scheduled_start, category="appointment",
            title=f"Upcoming: {appt.reason} with {appt.doctor.full_name}", source_type="appointment",
            source_id=appt.id))

    if since_dt:
        events = [e for e in events if e.at >= since_dt]
    if categories:
        events = [e for e in events if e.category in categories]
    events.sort(key=lambda e: e.at, reverse=True)
    return events
