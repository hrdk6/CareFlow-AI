"""Appointment scheduling rules: availability windows, double-booking and state transitions.

Hospital time is UTC in this demo; availability templates are weekday -> [["HH:MM","HH:MM"], ...].
"""
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationFailedError
from app.models import Appointment, Doctor

LIVE = ("scheduled", "checked_in")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SLOT_MINUTES = 30

ALLOWED_TRANSITIONS = {
    "scheduled": {"checked_in", "cancelled", "no_show", "completed"},
    "checked_in": {"completed", "cancelled", "no_show"},
    "completed": set(), "cancelled": set(), "no_show": set(),
}


def _windows(doctor: Doctor, day: date) -> list[tuple[datetime, datetime]]:
    out = []
    for start, end in (doctor.availability or {}).get(DAYS[day.weekday()], []):
        s, e = time.fromisoformat(start), time.fromisoformat(end)
        out.append((datetime.combine(day, s, tzinfo=UTC), datetime.combine(day, e, tzinfo=UTC)))
    return out


def within_availability(doctor: Doctor, start: datetime, minutes: int) -> bool:
    end = start + timedelta(minutes=minutes)
    return any(ws <= start and end <= we for ws, we in _windows(doctor, start.date()))


def overlapping(db: Session, *, start: datetime, minutes: int, doctor_id: int | None = None,
                patient_id: int | None = None, exclude_id: int | None = None) -> Appointment | None:
    end = start + timedelta(minutes=minutes)
    stmt = select(Appointment).where(Appointment.status.in_(LIVE), Appointment.scheduled_start < end,
                                     Appointment.scheduled_start > start - timedelta(minutes=240))
    if doctor_id is not None:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if patient_id is not None:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    for appt in db.scalars(stmt):
        if appt.scheduled_start + timedelta(minutes=appt.duration_minutes) > start:
            return appt
    return None


def validate_slot(db: Session, doctor: Doctor, patient_id: int, start: datetime, minutes: int,
                  appointment_type: str, exclude_id: int | None = None) -> None:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if appointment_type != "emergency":
        if start < datetime.now(UTC):
            raise ValidationFailedError("Appointments must be scheduled in the future")
        if not within_availability(doctor, start, minutes):
            raise ValidationFailedError(f"{doctor.full_name} is not available at that time")
    if not doctor.is_active:
        raise ValidationFailedError("This doctor is not currently accepting appointments")
    # Lock the doctor's row so two concurrent bookings cannot both pass the overlap check.
    db.execute(select(Doctor.id).where(Doctor.id == doctor.id).with_for_update())
    if overlapping(db, start=start, minutes=minutes, doctor_id=doctor.id, exclude_id=exclude_id):
        raise ConflictError(f"{doctor.full_name} already has an appointment at that time")
    if overlapping(db, start=start, minutes=minutes, patient_id=patient_id, exclude_id=exclude_id):
        raise ConflictError("The patient already has an appointment that overlaps this time")


def free_slots(db: Session, doctor: Doctor, day: date) -> list[tuple[datetime, datetime]]:
    booked = db.scalars(select(Appointment).where(and_(
        Appointment.doctor_id == doctor.id, Appointment.status.in_(LIVE),
        Appointment.scheduled_start >= datetime.combine(day, time.min, tzinfo=UTC),
        Appointment.scheduled_start < datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)))).all()
    now = datetime.now(UTC)
    slots = []
    for ws, we in _windows(doctor, day):
        t = ws
        while t + timedelta(minutes=SLOT_MINUTES) <= we:
            end = t + timedelta(minutes=SLOT_MINUTES)
            clash = any(b.scheduled_start < end and b.scheduled_start + timedelta(minutes=b.duration_minutes) > t
                        for b in booked)
            if not clash and t > now:
                slots.append((t, end))
            t = end
    return slots
