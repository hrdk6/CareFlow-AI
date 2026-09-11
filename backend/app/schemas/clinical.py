from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DepartmentOut(ORMModel):
    id: int
    code: str
    name: str
    description: str


class DoctorOut(ORMModel):
    id: int
    staff_code: str
    full_name: str
    specialty: str
    department_id: int
    department: str
    email: str
    phone: str
    availability: dict
    is_active: bool


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    scheduled_start: datetime
    duration_minutes: int = Field(default=30, ge=5, le=240)
    appointment_type: Literal["outpatient", "follow_up", "emergency", "telehealth"] = "outpatient"
    reason: str = Field(min_length=3, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentUpdate(BaseModel):
    scheduled_start: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
    status: Literal["checked_in", "completed", "no_show"] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class AppointmentOut(ORMModel):
    id: int
    patient_id: int
    patient_mrn: str
    patient_name: str
    doctor_id: int
    doctor_name: str
    department_id: int
    scheduled_start: datetime
    duration_minutes: int
    appointment_type: str
    reason: str
    status: str
    notes: str | None
    cancellation_reason: str | None


class SlotOut(BaseModel):
    start: datetime
    end: datetime


class AdmissionCreate(BaseModel):
    patient_id: int
    department_id: int
    attending_doctor_id: int
    admission_type: Literal["emergency", "urgent", "elective"]
    admission_source: Literal["emergency_room", "physician_referral", "transfer", "clinic"]
    reason: str = Field(min_length=3, max_length=255)
    ward: str | None = Field(default=None, max_length=32)


class DischargeIn(BaseModel):
    discharge_disposition: Literal["home", "home_health", "skilled_nursing", "rehab", "transfer", "ama", "expired"]


class AdmissionOut(ORMModel):
    id: int
    patient_id: int
    department_id: int
    department: str
    attending_doctor_id: int | None
    attending_doctor: str | None
    admitted_at: datetime
    discharged_at: datetime | None
    admission_type: str
    admission_source: str
    reason: str
    discharge_disposition: str | None
    status: str
    ward: str | None
    length_of_stay_days: float | None


class MedicalRecordCreate(BaseModel):
    patient_id: int
    visit_date: date
    record_type: Literal["consultation", "progress_note", "discharge_summary", "emergency", "follow_up"]
    chief_complaint: str = Field(min_length=3, max_length=255)
    symptoms: str | None = Field(default=None, max_length=4000)
    diagnosis_summary: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)
    treatment_plan: str | None = Field(default=None, max_length=4000)
    admission_id: int | None = None


class MedicalRecordOut(ORMModel):
    id: int
    patient_id: int
    patient_mrn: str | None = None
    doctor_id: int | None
    doctor_name: str | None
    admission_id: int | None
    visit_date: date
    record_type: str
    chief_complaint: str
    symptoms: str | None
    diagnosis_summary: str | None
    notes: str | None
    treatment_plan: str | None


class MedicationOut(ORMModel):
    id: int
    name: str
    drug_class: str
    is_high_alert: bool
    default_route: str


class PrescriptionCreate(BaseModel):
    patient_id: int
    medication_id: int
    dosage: str = Field(min_length=1, max_length=64)
    frequency: str = Field(min_length=1, max_length=64)
    start_date: date
    duration_days: int | None = Field(default=None, gt=0, le=3650)
    instructions: str | None = Field(default=None, max_length=1000)
    admission_id: int | None = None


class PrescriptionDiscontinue(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class PrescriptionOut(ORMModel):
    id: int
    patient_id: int
    patient_mrn: str | None = None
    medication_id: int
    medication: str
    drug_class: str
    is_high_alert: bool
    dosage: str
    frequency: str
    route: str
    duration_days: int | None
    instructions: str | None
    start_date: date
    end_date: date | None
    status: str
    doctor_name: str
    admission_id: int | None
    change_reason: str | None


class LabReportCreate(BaseModel):
    patient_id: int
    test_code: str = Field(min_length=1, max_length=16)
    value: float | None = None
    value_text: str | None = Field(default=None, max_length=128)
    collected_at: datetime
    admission_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class LabReportOut(ORMModel):
    id: int
    patient_id: int
    patient_mrn: str | None = None
    admission_id: int | None
    test_code: str
    test_name: str
    value: float | None
    value_text: str | None
    unit: str | None
    reference_low: float | None
    reference_high: float | None
    flag: str
    collected_at: datetime
    reported_at: datetime | None
    document_id: int | None


class TimelineEvent(BaseModel):
    id: str
    at: datetime
    category: Literal["admission", "discharge", "visit", "emergency", "diagnosis", "medication_start",
                      "medication_change", "medication_stop", "lab_abnormal", "appointment"]
    title: str
    detail: str | None = None
    source_type: str
    source_id: int
    severity: Literal["info", "warning", "critical"] = "info"


class TimelineOut(BaseModel):
    patient_id: int
    generated_at: datetime
    events: list[TimelineEvent]
