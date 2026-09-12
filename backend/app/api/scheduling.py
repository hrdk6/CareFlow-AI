"""Doctors, departments and appointments."""
import re
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.deps import DB, appointment_out, policy_for
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import Perm
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import Appointment, Department, Doctor, Patient, User
from app.schemas.clinical import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    DepartmentOut,
    DoctorCreate,
    DoctorOut,
    DoctorUpdate,
    SlotOut,
)
from app.schemas.common import Page
from app.services.appointments import ALLOWED_TRANSITIONS, LIVE, free_slots, validate_slot

router = APIRouter(tags=["scheduling"])
DoctorsRead = Depends(require(Perm.DOCTORS_READ))
DoctorsManage = Depends(require(Perm.USERS_MANAGE))  # staff records are administration, not clinical work

# Seeded convention: a weekday template of two clinics per day.
DEFAULT_AVAILABILITY = {d: [["09:00", "13:00"], ["14:00", "17:00"]] for d in ("mon", "tue", "wed", "thu", "fri")}


def doctor_out(d: Doctor) -> DoctorOut:
    return DoctorOut(id=d.id, staff_code=d.staff_code, full_name=d.full_name, specialty=d.specialty,
                     department_id=d.department_id, department=d.department.name, email=d.email, phone=d.phone,
                     availability=d.availability, is_active=d.is_active)


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: DB, user: User = DoctorsRead) -> list[DepartmentOut]:
    return [DepartmentOut.model_validate(d) for d in db.scalars(select(Department).order_by(Department.name))]


@router.get("/doctors", response_model=list[DoctorOut])
def list_doctors(db: DB, user: User = DoctorsRead, department_id: int | None = None,
                 q: str | None = Query(None, max_length=64)) -> list[DoctorOut]:
    stmt = select(Doctor)
    if department_id:
        stmt = stmt.where(Doctor.department_id == department_id)
    if q:
        stmt = stmt.where(or_(Doctor.full_name.ilike(f"%{q}%"), Doctor.specialty.ilike(f"%{q}%")))
    return [doctor_out(d) for d in db.scalars(stmt.order_by(Doctor.full_name))]


def _staff_code(db: DB, department_id: int) -> str:
    """Staff codes follow the seeded convention D<department><sequence>, e.g. D103."""
    n = db.scalar(select(func.count()).select_from(Doctor).where(Doctor.department_id == department_id)) or 0
    while True:
        n += 1
        code = f"D{department_id}{n:02d}"
        if db.scalar(select(Doctor.id).where(Doctor.staff_code == code)) is None:
            return code


@router.post("/doctors", response_model=DoctorOut, status_code=201)
def create_doctor(body: DoctorCreate, db: DB, user: User = DoctorsManage) -> DoctorOut:
    """Register a clinician. The profile is what appointments and care teams point at; a login account
    for this person is created separately (POST /admin/users with this doctor's id)."""
    department = db.get(Department, body.department_id)
    if department is None:
        raise ValidationFailedError("Unknown department")
    code = _staff_code(db, body.department_id)
    surname = re.sub(r"[^a-z]", "", body.full_name.split()[-1].lower()) or "staff"
    doctor = Doctor(staff_code=code, full_name=body.full_name.strip(), specialty=body.specialty.strip(),
                    department_id=body.department_id, email=body.email or f"{surname}.{code.lower()}@careflow.demo",
                    phone=body.phone, availability=body.availability or DEFAULT_AVAILABILITY, is_active=True)
    db.add(doctor)
    db.flush()
    audit("doctor.create", user=user, resource_type="doctor", resource_id=doctor.id,
          details={"staff_code": code, "department": department.name})
    return doctor_out(doctor)


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: DB, user: User = DoctorsRead) -> DoctorOut:
    d = db.get(Doctor, doctor_id)
    if d is None:
        raise NotFoundError("Doctor not found")
    return doctor_out(d)


@router.patch("/doctors/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, body: DoctorUpdate, db: DB, user: User = DoctorsManage) -> DoctorOut:
    """Transfer, reschedule or retire a clinician. Deactivating hides them from booking (validate_slot),
    so the diary must be empty first - otherwise patients hold appointments nobody will attend."""
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError("Doctor not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("department_id") is not None and db.get(Department, changes["department_id"]) is None:
        raise ValidationFailedError("Unknown department")
    if changes.get("is_active") is False and doctor.is_active:
        upcoming = db.scalar(select(func.count()).select_from(Appointment).where(
            Appointment.doctor_id == doctor.id, Appointment.status.in_(LIVE),
            Appointment.scheduled_start >= datetime.now(UTC)))
        if upcoming:
            raise ConflictError(f"{doctor.full_name} still has {upcoming} upcoming appointment(s); cancel or "
                                f"reassign them before deactivating the profile")
    for field, value in changes.items():
        setattr(doctor, field, value)
    if "department_id" in changes:
        # The linked account sees patients of its department, so a transfer has to move that too.
        linked = db.scalar(select(User).where(User.doctor_id == doctor.id))
        if linked is not None:
            linked.department_id = doctor.department_id
    db.flush()
    db.refresh(doctor)  # department is a joined relationship; reload it so a transfer is reflected
    audit("doctor.update", user=user, resource_type="doctor", resource_id=doctor.id,
          details={"fields": sorted(changes), "is_active": doctor.is_active})
    return doctor_out(doctor)


@router.get("/doctors/{doctor_id}/availability", response_model=list[SlotOut])
def doctor_availability(doctor_id: int, day: date, db: DB, user: User = DoctorsRead) -> list[SlotOut]:
    d = db.get(Doctor, doctor_id)
    if d is None:
        raise NotFoundError("Doctor not found")
    return [SlotOut(start=s, end=e) for s, e in free_slots(db, d, day)]


@router.get("/appointments", response_model=Page[AppointmentOut])
def list_appointments(db: DB, user: User = Depends(require(Perm.APPOINTMENTS_READ)),
                      date_from: datetime | None = None, date_to: datetime | None = None,
                      doctor_id: int | None = None, patient_id: int | None = None,
                      status: str | None = Query(None, pattern="^(scheduled|checked_in|completed|cancelled|no_show)$"),
                      limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[AppointmentOut]:
    policy = policy_for(db, user)
    stmt = select(Appointment).join(Patient, Patient.id == Appointment.patient_id).where(policy.patient_predicate())
    if date_from:
        stmt = stmt.where(Appointment.scheduled_start >= date_from)
    if date_to:
        stmt = stmt.where(Appointment.scheduled_start < date_to)
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if status:
        stmt = stmt.where(Appointment.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Appointment.scheduled_start).limit(limit).offset(offset))
    return Page(items=[appointment_out(a) for a in rows], total=total, limit=limit, offset=offset)


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(body: AppointmentCreate, db: DB,
                       user: User = Depends(require(Perm.APPOINTMENTS_WRITE))) -> AppointmentOut:
    patient = policy_for(db, user).get_patient(body.patient_id, clinical=False)
    doctor = db.get(Doctor, body.doctor_id)
    if doctor is None:
        raise ValidationFailedError("Unknown doctor")
    start = body.scheduled_start if body.scheduled_start.tzinfo else body.scheduled_start.replace(tzinfo=UTC)
    validate_slot(db, doctor, patient.id, start, body.duration_minutes, body.appointment_type)
    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, department_id=doctor.department_id,
                       scheduled_start=start, duration_minutes=body.duration_minutes,
                       appointment_type=body.appointment_type, reason=body.reason, notes=body.notes,
                       status="scheduled", created_by_user_id=user.id)
    db.add(appt)
    db.flush()
    db.refresh(appt)
    audit("appointment.create", user=user, resource_type="appointment", resource_id=appt.id, patient_id=patient.id)
    return appointment_out(appt)


def _appointment(db, user, appointment_id: int) -> Appointment:
    appt = db.get(Appointment, appointment_id)
    if appt is None:
        raise NotFoundError("Appointment not found")
    policy_for(db, user).get_patient(appt.patient_id, clinical=False)  # same visibility as the patient
    return appt


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, body: AppointmentUpdate, db: DB,
                       user: User = Depends(require(Perm.APPOINTMENTS_WRITE))) -> AppointmentOut:
    appt = _appointment(db, user, appointment_id)
    if appt.status not in ("scheduled", "checked_in"):
        raise ValidationFailedError(f"A {appt.status} appointment cannot be modified")
    if body.scheduled_start or body.duration_minutes:
        start = body.scheduled_start or appt.scheduled_start
        start = start if start.tzinfo else start.replace(tzinfo=UTC)
        minutes = body.duration_minutes or appt.duration_minutes
        validate_slot(db, appt.doctor, appt.patient_id, start, minutes, appt.appointment_type, exclude_id=appt.id)
        appt.scheduled_start, appt.duration_minutes = start, minutes
    if body.status:
        if body.status not in ALLOWED_TRANSITIONS[appt.status]:
            raise ValidationFailedError(f"Cannot change status from {appt.status} to {body.status}")
        appt.status = body.status
    if body.notes is not None:
        appt.notes = body.notes
    db.flush()
    audit("appointment.update", user=user, resource_type="appointment", resource_id=appt.id,
          patient_id=appt.patient_id, details={"fields": sorted(body.model_dump(exclude_unset=True))})
    return appointment_out(appt)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: int, body: AppointmentCancel, db: DB,
                       user: User = Depends(require(Perm.APPOINTMENTS_WRITE))) -> AppointmentOut:
    appt = _appointment(db, user, appointment_id)
    if "cancelled" not in ALLOWED_TRANSITIONS[appt.status]:
        raise ValidationFailedError(f"A {appt.status} appointment cannot be cancelled")
    appt.status, appt.cancellation_reason = "cancelled", body.reason
    db.flush()
    audit("appointment.cancel", user=user, resource_type="appointment", resource_id=appt.id, patient_id=appt.patient_id)
    return appointment_out(appt)
