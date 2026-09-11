"""Shared API dependencies and serializers."""
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models import Admission, Appointment, LabReport, MedicalRecord, Patient, Prescription, User
from app.schemas.clinical import AdmissionOut, AppointmentOut, LabReportOut, MedicalRecordOut, PrescriptionOut
from app.schemas.patients import PatientDemographics, PatientListItem

DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def policy_for(db: Session, user: User) -> AccessPolicy:
    return AccessPolicy(db, user)


def age_of(dob: date) -> int:
    today = datetime.now(UTC).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def patient_item(p: Patient) -> PatientListItem:
    return PatientListItem(id=p.id, mrn=p.mrn, full_name=p.full_name, date_of_birth=p.date_of_birth,
                           age=age_of(p.date_of_birth), sex=p.sex, status=p.status,
                           primary_department=p.primary_department.name if p.primary_department else None,
                           phone=p.phone, is_synthetic=p.is_synthetic)


def patient_demographics(p: Patient) -> PatientDemographics:
    return PatientDemographics(**patient_item(p).model_dump(), first_name=p.first_name, last_name=p.last_name,
                               email=p.email, address=p.address, preferred_language=p.preferred_language,
                               emergency_contact_name=p.emergency_contact_name,
                               emergency_contact_phone=p.emergency_contact_phone,
                               emergency_contact_relation=p.emergency_contact_relation, created_at=p.created_at)


def appointment_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(id=a.id, patient_id=a.patient_id, patient_mrn=a.patient.mrn, patient_name=a.patient.full_name,
                          doctor_id=a.doctor_id, doctor_name=a.doctor.full_name, department_id=a.department_id,
                          scheduled_start=a.scheduled_start, duration_minutes=a.duration_minutes,
                          appointment_type=a.appointment_type, reason=a.reason, status=a.status, notes=a.notes,
                          cancellation_reason=a.cancellation_reason)


def admission_out(a: Admission) -> AdmissionOut:
    return AdmissionOut(id=a.id, patient_id=a.patient_id, department_id=a.department_id, department=a.department.name,
                        attending_doctor_id=a.attending_doctor_id,
                        attending_doctor=a.attending_doctor.full_name if a.attending_doctor else None,
                        admitted_at=a.admitted_at, discharged_at=a.discharged_at, admission_type=a.admission_type,
                        admission_source=a.admission_source, reason=a.reason,
                        discharge_disposition=a.discharge_disposition, status=a.status, ward=a.ward,
                        length_of_stay_days=a.length_of_stay_days)


def record_out(r: MedicalRecord, mrn: str | None = None) -> MedicalRecordOut:
    return MedicalRecordOut(id=r.id, patient_id=r.patient_id, patient_mrn=mrn, doctor_id=r.doctor_id,
                            doctor_name=r.doctor.full_name if r.doctor else None, admission_id=r.admission_id,
                            visit_date=r.visit_date, record_type=r.record_type, chief_complaint=r.chief_complaint,
                            symptoms=r.symptoms, diagnosis_summary=r.diagnosis_summary, notes=r.notes,
                            treatment_plan=r.treatment_plan)


def prescription_out(rx: Prescription, mrn: str | None = None) -> PrescriptionOut:
    m = rx.medication
    return PrescriptionOut(id=rx.id, patient_id=rx.patient_id, patient_mrn=mrn, medication_id=m.id, medication=m.name,
                           drug_class=m.drug_class, is_high_alert=m.is_high_alert, dosage=rx.dosage,
                           frequency=rx.frequency, route=rx.route, duration_days=rx.duration_days,
                           instructions=rx.instructions, start_date=rx.start_date, end_date=rx.end_date,
                           status=rx.status, doctor_name=rx.doctor.full_name, admission_id=rx.admission_id,
                           change_reason=rx.change_reason)


def lab_out(lab: LabReport, mrn: str | None = None) -> LabReportOut:
    return LabReportOut.model_validate({**{c: getattr(lab, c) for c in LabReportOut.model_fields if hasattr(lab, c)},
                                        "patient_mrn": mrn})
