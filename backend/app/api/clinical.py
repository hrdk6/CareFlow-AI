"""Cross-patient clinical lists and clinical write operations (records, prescriptions, labs, admissions)."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DB, admission_out, lab_out, policy_for, prescription_out, record_out
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import Perm
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import Admission, Department, Doctor, LabReport, MedicalRecord, Medication, Patient, Prescription, User
from app.schemas.clinical import (
    AdmissionCreate,
    AdmissionOut,
    DischargeIn,
    LabReportCreate,
    LabReportOut,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicationOut,
    PrescriptionCreate,
    PrescriptionDiscontinue,
    PrescriptionOut,
)
from app.schemas.common import Page
from app.seed.catalog import LABS

router = APIRouter(tags=["clinical"])
Clinical = Depends(require(Perm.PATIENTS_READ_CLINICAL))


def _doctor_for(db, user: User) -> Doctor | None:
    return db.get(Doctor, user.doctor_id) if user.doctor_id else None


def _mrns(db, ids: set[int]) -> dict[int, str]:
    return dict(db.execute(select(Patient.id, Patient.mrn).where(Patient.id.in_(ids))).all()) if ids else {}


# ------------------------------------------------------------------ medical records
@router.get("/records", response_model=Page[MedicalRecordOut])
def list_records(db: DB, user: User = Clinical, patient_id: int | None = None,
                 record_type: str | None = Query(None, max_length=32), limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0)) -> Page[MedicalRecordOut]:
    stmt = select(MedicalRecord).where(MedicalRecord.patient_id.in_(policy_for(db, user).clinical_patient_ids()))
    if patient_id:
        stmt = stmt.where(MedicalRecord.patient_id == patient_id)
    if record_type:
        stmt = stmt.where(MedicalRecord.record_type == record_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(MedicalRecord.visit_date.desc(), MedicalRecord.id.desc()).limit(limit).offset(offset)).all()
    mrns = _mrns(db, {r.patient_id for r in rows})
    audit("records.list", user=user, details={"count": len(rows), "patient_id": patient_id})
    return Page(items=[record_out(r, mrns.get(r.patient_id)) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/records", response_model=MedicalRecordOut, status_code=201)
def create_record(body: MedicalRecordCreate, db: DB, user: User = Depends(require(Perm.CLINICAL_WRITE))) -> MedicalRecordOut:
    p = policy_for(db, user).get_patient(body.patient_id, clinical=True)
    if body.admission_id and db.scalar(select(Admission.id).where(Admission.id == body.admission_id,
                                                                  Admission.patient_id == p.id)) is None:
        raise ValidationFailedError("Admission does not belong to this patient")
    doctor = _doctor_for(db, user)
    rec = MedicalRecord(**body.model_dump(), doctor_id=doctor.id if doctor else None)
    db.add(rec)
    db.flush()
    db.refresh(rec)
    audit("record.create", user=user, resource_type="medical_record", resource_id=rec.id, patient_id=p.id)
    return record_out(rec, p.mrn)


# ------------------------------------------------------------------ prescriptions
@router.get("/medications", response_model=list[MedicationOut])
def formulary(db: DB, user: User = Clinical) -> list[MedicationOut]:
    return [MedicationOut.model_validate(m) for m in db.scalars(select(Medication).order_by(Medication.name))]


@router.get("/prescriptions", response_model=Page[PrescriptionOut])
def list_prescriptions(db: DB, user: User = Clinical, patient_id: int | None = None,
                       status: str | None = Query(None, pattern="^(active|completed|discontinued)$"),
                       high_alert: bool | None = None, limit: int = Query(50, ge=1, le=200),
                       offset: int = Query(0, ge=0)) -> Page[PrescriptionOut]:
    stmt = (select(Prescription).join(Medication)
            .where(Prescription.patient_id.in_(policy_for(db, user).clinical_patient_ids()),
                   Prescription.admission_id.is_(None)))
    if patient_id:
        stmt = stmt.where(Prescription.patient_id == patient_id)
    if status:
        stmt = stmt.where(Prescription.status == status)
    if high_alert is not None:
        stmt = stmt.where(Medication.is_high_alert.is_(high_alert))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Prescription.start_date.desc()).limit(limit).offset(offset)).all()
    mrns = _mrns(db, {r.patient_id for r in rows})
    return Page(items=[prescription_out(r, mrns.get(r.patient_id)) for r in rows], total=total, limit=limit,
                offset=offset)


@router.post("/prescriptions", response_model=PrescriptionOut, status_code=201)
def create_prescription(body: PrescriptionCreate, db: DB,
                        user: User = Depends(require(Perm.PRESCRIPTIONS_WRITE))) -> PrescriptionOut:
    p = policy_for(db, user).get_patient(body.patient_id, clinical=True)
    med = db.get(Medication, body.medication_id)
    if med is None:
        raise ValidationFailedError("Unknown medication")
    doctor = _doctor_for(db, user)
    if doctor is None:
        raise ValidationFailedError("Only users linked to a doctor profile can prescribe")
    allergies = {a["substance"].lower() for a in p.allergies}
    if "penicillin" in allergies and med.name in ("amoxicillin", "cefazolin", "ceftriaxone"):
        # Cross-reactivity check is advisory in real systems; here it is a hard stop to demonstrate the control.
        raise ConflictError(f"Allergy alert: patient has a documented penicillin allergy; review before prescribing "
                            f"{med.name}.")
    if db.scalar(select(Prescription.id).where(Prescription.patient_id == p.id, Prescription.medication_id == med.id,
                                               Prescription.status == "active", Prescription.admission_id.is_(None))):
        raise ConflictError(f"{med.name} is already active for this patient; discontinue or change it instead")
    end = None
    if body.duration_days:
        from datetime import timedelta

        end = body.start_date + timedelta(days=body.duration_days - 1)
    rx = Prescription(patient_id=p.id, medication_id=med.id, doctor_id=doctor.id, admission_id=body.admission_id,
                      dosage=body.dosage, frequency=body.frequency, route=med.default_route,
                      duration_days=body.duration_days, instructions=body.instructions, start_date=body.start_date,
                      end_date=end, status="active")
    db.add(rx)
    db.flush()
    db.refresh(rx)
    audit("prescription.create", user=user, resource_type="prescription", resource_id=rx.id, patient_id=p.id,
          details={"medication": med.name, "high_alert": med.is_high_alert})
    return prescription_out(rx, p.mrn)


@router.post("/prescriptions/{prescription_id}/discontinue", response_model=PrescriptionOut)
def discontinue_prescription(prescription_id: int, body: PrescriptionDiscontinue, db: DB,
                             user: User = Depends(require(Perm.PRESCRIPTIONS_WRITE))) -> PrescriptionOut:
    rx = db.get(Prescription, prescription_id)
    if rx is None:
        raise NotFoundError("Prescription not found")
    p = policy_for(db, user).get_patient(rx.patient_id, clinical=True)
    if rx.status != "active":
        raise ValidationFailedError("Only active prescriptions can be discontinued")
    rx.status, rx.end_date, rx.change_reason = "discontinued", datetime.now(UTC).date(), f"Stopped - {body.reason}"
    db.flush()
    audit("prescription.discontinue", user=user, resource_type="prescription", resource_id=rx.id, patient_id=p.id)
    return prescription_out(rx, p.mrn)


# ------------------------------------------------------------------ laboratory
@router.get("/labs", response_model=Page[LabReportOut])
def list_labs(db: DB, user: User = Clinical, patient_id: int | None = None, test_code: str | None = None,
              flag: str | None = Query(None, pattern="^(normal|low|high|critical)$"),
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[LabReportOut]:
    stmt = select(LabReport).where(LabReport.patient_id.in_(policy_for(db, user).clinical_patient_ids()))
    if patient_id:
        stmt = stmt.where(LabReport.patient_id == patient_id)
    if test_code:
        stmt = stmt.where(LabReport.test_code == test_code.upper())
    if flag:
        stmt = stmt.where(LabReport.flag == flag)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(LabReport.collected_at.desc()).limit(limit).offset(offset)).all()
    mrns = _mrns(db, {r.patient_id for r in rows})
    return Page(items=[lab_out(r, mrns.get(r.patient_id)) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/labs/catalog")
def lab_catalog(user: User = Clinical) -> list[dict]:
    return [{"code": lab.code, "name": lab.name, "unit": lab.unit, "reference_low": lab.low,
             "reference_high": lab.high} for lab in LABS.values()]


@router.post("/labs", response_model=LabReportOut, status_code=201)
def create_lab(body: LabReportCreate, db: DB, user: User = Depends(require(Perm.CLINICAL_WRITE))) -> LabReportOut:
    p = policy_for(db, user).get_patient(body.patient_id, clinical=True)
    spec = LABS.get(body.test_code.upper())
    if spec is None:
        raise ValidationFailedError(f"Unknown test code. Known codes: {', '.join(LABS)}")
    if body.value is None and not body.value_text:
        raise ValidationFailedError("Provide a numeric value or a text result")
    flag = "normal"
    if body.value is not None:
        v = body.value
        if spec.low is not None and v < spec.low:
            flag = "low"
        if spec.high is not None and v > spec.high:
            flag = "high"
        if (spec.critical_low is not None and v <= spec.critical_low) or (
                spec.critical_high is not None and v >= spec.critical_high):
            flag = "critical"
    lab = LabReport(patient_id=p.id, admission_id=body.admission_id, ordered_by_doctor_id=user.doctor_id,
                    test_code=spec.code, test_name=spec.name, value=body.value, value_text=body.value_text,
                    unit=spec.unit, reference_low=spec.low, reference_high=spec.high, flag=flag,
                    collected_at=body.collected_at, reported_at=datetime.now(UTC), notes=body.notes)
    db.add(lab)
    db.flush()
    db.refresh(lab)
    audit("lab.create", user=user, resource_type="lab_report", resource_id=lab.id, patient_id=p.id,
          details={"test": spec.code, "flag": flag})
    return lab_out(lab, p.mrn)


# ------------------------------------------------------------------ admissions
@router.get("/admissions", response_model=list[AdmissionOut])
def list_admissions(db: DB, user: User = Clinical,
                    status: str | None = Query(None, pattern="^(admitted|discharged)$"),
                    department_id: int | None = None, limit: int = Query(100, ge=1, le=500)) -> list[AdmissionOut]:
    stmt = select(Admission).where(Admission.patient_id.in_(policy_for(db, user).clinical_patient_ids()))
    if status:
        stmt = stmt.where(Admission.status == status)
    if department_id:
        stmt = stmt.where(Admission.department_id == department_id)
    return [admission_out(a) for a in db.scalars(stmt.order_by(Admission.admitted_at.desc()).limit(limit))]


@router.post("/admissions", response_model=AdmissionOut, status_code=201)
def admit(body: AdmissionCreate, db: DB, user: User = Depends(require(Perm.ADMISSIONS_WRITE))) -> AdmissionOut:
    p = policy_for(db, user).get_patient(body.patient_id, clinical=True)
    if db.scalar(select(Admission.id).where(Admission.patient_id == p.id, Admission.status == "admitted")):
        raise ConflictError("Patient is already admitted")
    if db.get(Department, body.department_id) is None or db.get(Doctor, body.attending_doctor_id) is None:
        raise ValidationFailedError("Unknown department or attending doctor")
    adm = Admission(**body.model_dump(), admitted_at=datetime.now(UTC), status="admitted")
    db.add(adm)
    p.status = "admitted"
    db.flush()
    db.refresh(adm)
    audit("admission.create", user=user, resource_type="admission", resource_id=adm.id, patient_id=p.id)
    return admission_out(adm)


@router.post("/admissions/{admission_id}/discharge", response_model=AdmissionOut)
def discharge(admission_id: int, body: DischargeIn, db: DB,
              user: User = Depends(require(Perm.ADMISSIONS_WRITE))) -> AdmissionOut:
    adm = db.get(Admission, admission_id)
    if adm is None:
        raise NotFoundError("Admission not found")
    p = policy_for(db, user).get_patient(adm.patient_id, clinical=True)
    if adm.status != "admitted":
        raise ValidationFailedError("Admission is already closed")
    adm.status, adm.discharged_at, adm.discharge_disposition = "discharged", datetime.now(UTC), body.discharge_disposition
    p.status = "deceased" if body.discharge_disposition == "expired" else "discharged"
    db.flush()
    audit("admission.discharge", user=user, resource_type="admission", resource_id=adm.id, patient_id=p.id)
    return admission_out(adm)
