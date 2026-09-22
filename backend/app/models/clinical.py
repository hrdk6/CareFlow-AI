"""Hospital domain: departments, staff, patients and clinical events."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def str_enum(*values: str, name: str) -> Enum:
    """VARCHAR + CHECK constraint (portable, migration-friendly) instead of a native PG enum."""
    return Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


DIAGNOSIS_CATEGORIES = (
    "circulatory", "respiratory", "digestive", "diabetes", "injury", "musculoskeletal",
    "genitourinary", "neoplasms", "other",
)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Doctor(TimestampMixin, Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_code: Mapped[str] = mapped_column(String(16), unique=True)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    specialty: Mapped[str] = mapped_column(String(64))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    # Weekly template, e.g. {"mon": [["09:00", "13:00"]], ...}
    availability: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped[Department] = relationship(lazy="joined")


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mrn: Mapped[str] = mapped_column(String(16), unique=True)  # e.g. P1024
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(str_enum("F", "M", "X", name="sex"))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(32), default="English")
    blood_type: Mapped[str | None] = mapped_column(String(4))
    emergency_contact_name: Mapped[str | None] = mapped_column(String(128))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32))
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(32))
    # [{"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"}]
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(
        str_enum("active", "admitted", "discharged", "inactive", "deceased", name="patient_status"),
        default="active",
        index=True,
    )
    primary_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    primary_department: Mapped[Department | None] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CareAssignment(Base):
    """Explicit care-team membership: the basis for nurse (and doctor) patient access."""

    __tablename__ = "care_assignments"
    __table_args__ = (UniqueConstraint("patient_id", "user_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    care_role: Mapped[str] = mapped_column(str_enum("attending", "consulting", "nurse", name="care_role"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 5 AND 240", name="duration_range"),
        Index("ix_appointments_doctor_start", "doctor_id", "scheduled_start"),
        # No two live appointments for the same doctor at the same start time.
        Index(
            "uq_appointments_doctor_slot",
            "doctor_id",
            "scheduled_start",
            unique=True,
            postgresql_where=text("status IN ('scheduled', 'checked_in')"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    appointment_type: Mapped[str] = mapped_column(
        str_enum("outpatient", "follow_up", "emergency", "telehealth", name="appointment_type"),
        default="outpatient",
    )
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        str_enum("scheduled", "checked_in", "completed", "cancelled", "no_show", name="appointment_status"),
        default="scheduled",
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    patient: Mapped[Patient] = relationship(lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")


class Admission(TimestampMixin, Base):
    __tablename__ = "admissions"
    __table_args__ = (
        CheckConstraint("discharged_at IS NULL OR discharged_at >= admitted_at", name="discharge_after_admit"),
        CheckConstraint(
            "(status = 'admitted' AND discharged_at IS NULL) OR (status = 'discharged' AND discharged_at IS NOT NULL)",
            name="status_matches_discharge",
        ),
        Index("ix_admissions_patient_admitted", "patient_id", "admitted_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    attending_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), index=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admission_type: Mapped[str] = mapped_column(str_enum("emergency", "urgent", "elective", name="admission_type"))
    admission_source: Mapped[str] = mapped_column(
        str_enum("emergency_room", "physician_referral", "transfer", "clinic", name="admission_source")
    )
    reason: Mapped[str] = mapped_column(String(255))
    discharge_disposition: Mapped[str | None] = mapped_column(
        str_enum("home", "home_health", "skilled_nursing", "rehab", "transfer", "ama", "expired",
                 name="discharge_disposition")
    )
    status: Mapped[str] = mapped_column(str_enum("admitted", "discharged", name="admission_status"), index=True)
    ward: Mapped[str | None] = mapped_column(String(32))

    department: Mapped[Department] = relationship(lazy="joined")
    attending_doctor: Mapped[Doctor | None] = relationship(lazy="joined")

    @property
    def length_of_stay_days(self) -> float | None:
        if self.discharged_at is None:
            return None
        return round((self.discharged_at - self.admitted_at).total_seconds() / 86400, 1)


class MedicalRecord(TimestampMixin, Base):
    __tablename__ = "medical_records"
    __table_args__ = (Index("ix_medical_records_patient_visit", "patient_id", "visit_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    visit_date: Mapped[date] = mapped_column(Date)
    record_type: Mapped[str] = mapped_column(
        str_enum("consultation", "progress_note", "discharge_summary", "radiology_report", "emergency",
                 "follow_up", name="record_type")
    )
    chief_complaint: Mapped[str] = mapped_column(String(255))
    symptoms: Mapped[str | None] = mapped_column(Text)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    treatment_plan: Mapped[str | None] = mapped_column(Text)
    # Discharge co-pilot provenance: drafting model, signer, share of the prose edited, and the source behind
    # every [R#]/[S#] marker kept in the text. NULL for records written by hand.
    ai_provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    doctor: Mapped[Doctor | None] = relationship(lazy="joined")


class Diagnosis(TimestampMixin, Base):
    __tablename__ = "diagnoses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    medical_record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    icd10_code: Mapped[str] = mapped_column(String(10), index=True)
    description: Mapped[str] = mapped_column(String(255))
    # Coarse clinical grouping (mirrors the grouping used by the readmission model).
    category: Mapped[str] = mapped_column(str_enum(*DIAGNOSIS_CATEGORIES, name="diagnosis_category"))
    is_chronic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(str_enum("active", "resolved", name="diagnosis_status"), default="active")
    diagnosed_on: Mapped[date] = mapped_column(Date)


class Medication(Base):
    """Formulary entry."""

    __tablename__ = "medications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    drug_class: Mapped[str] = mapped_column(String(64), index=True)
    is_high_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    default_route: Mapped[str] = mapped_column(String(16), default="oral")


class Prescription(TimestampMixin, Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="end_after_start"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="positive_duration"),
        Index("ix_prescriptions_patient_start", "patient_id", "start_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    dosage: Mapped[str] = mapped_column(String(64))
    frequency: Mapped[str] = mapped_column(String(64))
    route: Mapped[str] = mapped_column(String(16), default="oral")
    duration_days: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        str_enum("active", "completed", "discontinued", name="prescription_status"), default="active", index=True
    )
    change_reason: Mapped[str | None] = mapped_column(String(255))

    medication: Mapped[Medication] = relationship(lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")


class LabReport(TimestampMixin, Base):
    __tablename__ = "lab_reports"
    __table_args__ = (Index("ix_lab_reports_patient_collected", "patient_id", "collected_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    ordered_by_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    test_code: Mapped[str] = mapped_column(String(16), index=True)  # e.g. HBA1C
    test_name: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(128))
    unit: Mapped[str | None] = mapped_column(String(16))
    reference_low: Mapped[float | None] = mapped_column(Float)
    reference_high: Mapped[float | None] = mapped_column(Float)
    flag: Mapped[str] = mapped_column(str_enum("normal", "low", "high", "critical", name="lab_flag"), default="normal")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
