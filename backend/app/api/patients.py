from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.deps import (
    DB,
    admission_out,
    appointment_out,
    lab_out,
    patient_demographics,
    patient_item,
    policy_for,
    prescription_out,
    record_out,
)
from app.audit.service import audit
from app.auth.dependencies import require, require_any
from app.auth.rbac import Perm
from app.core.errors import PermissionDeniedError, ValidationFailedError
from app.llm.tools import care_team
from app.ml.service import predict_length_of_stay, predict_readmission
from app.models import (
    Admission,
    Appointment,
    Department,
    Diagnosis,
    Document,
    LabReport,
    MedicalRecord,
    MLPrediction,
    Patient,
    Prescription,
    User,
)
from app.schemas.clinical import (
    AdmissionOut,
    AppointmentOut,
    LabReportOut,
    MedicalRecordOut,
    PrescriptionOut,
    TimelineOut,
)
from app.schemas.common import Page
from app.schemas.documents import DocumentOut
from app.schemas.ml import PredictionOut, SimilarityOut
from app.schemas.patients import (
    CareTeamMember,
    DiagnosisOut,
    PatientClinical,
    PatientCreate,
    PatientDemographics,
    PatientListItem,
    PatientUpdate,
)
from app.services.similarity import similar_patients
from app.services.timeline import build_timeline

router = APIRouter(prefix="/patients", tags=["patients"])

Demographic = Depends(require(Perm.PATIENTS_READ_DEMOGRAPHICS))
Clinical = Depends(require(Perm.PATIENTS_READ_CLINICAL))


@router.get("", response_model=Page[PatientListItem])
def list_patients(db: DB, user: User = Demographic, q: str | None = Query(None, max_length=64),
                  status: str | None = Query(None, pattern="^(active|admitted|discharged|inactive|deceased)$"),
                  department_id: int | None = None, limit: int = Query(25, ge=1, le=200),
                  offset: int = Query(0, ge=0)) -> Page[PatientListItem]:
    policy = policy_for(db, user)
    stmt = select(Patient).where(policy.patient_predicate())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Patient.mrn.ilike(like), Patient.first_name.ilike(like), Patient.last_name.ilike(like),
                              (Patient.first_name + " " + Patient.last_name).ilike(like)))
    if status:
        stmt = stmt.where(Patient.status == status)
    if department_id:
        stmt = stmt.where(Patient.primary_department_id == department_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Patient.last_name, Patient.first_name).limit(limit).offset(offset)).all()
    return Page(items=[patient_item(p) for p in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=PatientDemographics, status_code=201)
def create_patient(body: PatientCreate, db: DB, user: User = Depends(require(Perm.PATIENTS_WRITE))) -> PatientDemographics:
    if body.primary_department_id and db.get(Department, body.primary_department_id) is None:
        raise ValidationFailedError("Unknown department")
    db.execute(select(func.pg_advisory_xact_lock(424242)))  # serialise MRN allocation
    last = db.scalar(select(func.max(func.cast(func.substr(Patient.mrn, 2), type_=Patient.id.type))))
    patient = Patient(mrn=f"P{(last or 1000) + 1:04d}", is_synthetic=True,
                      **body.model_dump(exclude={"allergies"}), allergies=[a.model_dump() for a in body.allergies])
    db.add(patient)
    db.flush()
    db.refresh(patient)
    audit("patient.create", user=user, resource_type="patient", resource_id=patient.id, patient_id=patient.id)
    return patient_demographics(patient)


@router.get("/{patient_id}", response_model=PatientClinical | PatientDemographics)
def get_patient(patient_id: int, db: DB, user: User = Demographic):
    policy = policy_for(db, user)
    p = policy.get_patient(patient_id, clinical=False)
    audit("patient.read", user=user, resource_type="patient", resource_id=p.id, patient_id=p.id,
          details={"view": "clinical" if policy.can_read_clinical else "demographics"})
    if not policy.can_read_clinical:
        return patient_demographics(p)
    dxs = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == p.id, Diagnosis.status == "active")
                     .order_by(Diagnosis.diagnosed_on)).all()
    meds = db.scalars(select(Prescription).where(Prescription.patient_id == p.id, Prescription.status == "active",
                                                 Prescription.admission_id.is_(None))).all()
    current = db.scalar(select(Admission).where(Admission.patient_id == p.id, Admission.status == "admitted"))
    n_adm = db.scalar(select(func.count()).select_from(Admission).where(Admission.patient_id == p.id))
    return PatientClinical(
        **patient_demographics(p).model_dump(), blood_type=p.blood_type, allergies=p.allergies,
        active_diagnoses=[DiagnosisOut.model_validate(d) for d in dxs],
        current_medications=[prescription_out(rx).model_dump(mode="json") for rx in meds],
        current_admission=admission_out(current).model_dump(mode="json") if current else None,
        admission_count=n_adm,
        care_team=[CareTeamMember(user_id=uid, name=name, care_role=role) for uid, name, role in care_team(db, p.id)])


@router.patch("/{patient_id}", response_model=PatientDemographics)
def update_patient(patient_id: int, body: PatientUpdate, db: DB,
                   user: User = Depends(require_any(Perm.PATIENTS_WRITE, Perm.CLINICAL_WRITE))) -> PatientDemographics:
    """Registration details and allergies live on the same record but belong to different roles:
    reception keeps contact details current, clinicians maintain the allergy list."""
    p = policy_for(db, user).get_patient(patient_id, clinical=False)
    changes = body.model_dump(exclude_unset=True)
    codes = user.permission_codes
    if "allergies" in changes and changes["allergies"] is not None:
        # Allergies drive the prescribing safety check, so only clinical staff may change them - a
        # registration role can capture them at intake but cannot silently overwrite them later.
        if Perm.CLINICAL_WRITE.value not in codes:
            raise PermissionDeniedError("Only clinical staff can change a patient's allergies")
        changes["allergies"] = [dict(a) for a in changes["allergies"]]
    if set(changes) - {"allergies"} and Perm.PATIENTS_WRITE.value not in codes:
        raise PermissionDeniedError("Your role cannot change patient registration details")
    for field, value in changes.items():
        setattr(p, field, value)
    db.flush()
    audit("patient.update", user=user, resource_type="patient", resource_id=p.id, patient_id=p.id,
          details={"fields": sorted(changes)})
    return patient_demographics(p)


def _clinical_patient(db, user, patient_id: int, action: str) -> Patient:
    p = policy_for(db, user).get_patient(patient_id, clinical=True)
    audit(action, user=user, resource_type="patient", resource_id=p.id, patient_id=p.id)
    return p


@router.get("/{patient_id}/records", response_model=list[MedicalRecordOut])
def patient_records(patient_id: int, db: DB, user: User = Clinical,
                    limit: int = Query(50, ge=1, le=500)) -> list[MedicalRecordOut]:
    p = _clinical_patient(db, user, patient_id, "patient.records.read")
    rows = db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == p.id)
                      .order_by(MedicalRecord.visit_date.desc(), MedicalRecord.id.desc()).limit(limit))
    return [record_out(r, p.mrn) for r in rows]


@router.get("/{patient_id}/timeline", response_model=TimelineOut)
def patient_timeline(patient_id: int, db: DB, user: User = Clinical,
                     months: int = Query(36, ge=1, le=240)) -> TimelineOut:
    p = _clinical_patient(db, user, patient_id, "patient.timeline.read")
    since = datetime.now(UTC).date() - timedelta(days=30 * months)
    return TimelineOut(patient_id=p.id, generated_at=datetime.now(UTC), events=build_timeline(db, p.id, since=since))


@router.get("/{patient_id}/admissions", response_model=list[AdmissionOut])
def patient_admissions(patient_id: int, db: DB, user: User = Clinical) -> list[AdmissionOut]:
    p = _clinical_patient(db, user, patient_id, "patient.admissions.read")
    return [admission_out(a) for a in db.scalars(select(Admission).where(Admission.patient_id == p.id)
                                                 .order_by(Admission.admitted_at.desc()))]


@router.get("/{patient_id}/prescriptions", response_model=list[PrescriptionOut])
def patient_prescriptions(patient_id: int, db: DB, user: User = Clinical,
                          include_inpatient: bool = False) -> list[PrescriptionOut]:
    p = _clinical_patient(db, user, patient_id, "patient.prescriptions.read")
    stmt = select(Prescription).where(Prescription.patient_id == p.id)
    if not include_inpatient:
        stmt = stmt.where(Prescription.admission_id.is_(None))
    return [prescription_out(rx, p.mrn) for rx in db.scalars(stmt.order_by(Prescription.start_date.desc()))]


@router.get("/{patient_id}/labs", response_model=list[LabReportOut])
def patient_labs(patient_id: int, db: DB, user: User = Clinical, test_code: str | None = None,
                 limit: int = Query(300, ge=1, le=2000)) -> list[LabReportOut]:
    p = _clinical_patient(db, user, patient_id, "patient.labs.read")
    stmt = select(LabReport).where(LabReport.patient_id == p.id)
    if test_code:
        stmt = stmt.where(LabReport.test_code == test_code.upper())
    return [lab_out(lab, p.mrn) for lab in db.scalars(stmt.order_by(LabReport.collected_at.desc()).limit(limit))]


@router.get("/{patient_id}/appointments", response_model=list[AppointmentOut])
def patient_appointments(patient_id: int, db: DB,
                         user: User = Depends(require(Perm.APPOINTMENTS_READ))) -> list[AppointmentOut]:
    p = policy_for(db, user).get_patient(patient_id, clinical=False)
    rows = db.scalars(select(Appointment).where(Appointment.patient_id == p.id)
                      .order_by(Appointment.scheduled_start.desc()).limit(200))
    return [appointment_out(a) for a in rows]


@router.get("/{patient_id}/documents", response_model=list[DocumentOut])
def patient_documents(patient_id: int, db: DB, user: User = Clinical) -> list[DocumentOut]:
    policy = policy_for(db, user)
    p = policy.get_patient(patient_id, clinical=True)
    rows = db.scalars(select(Document).where(Document.patient_id == p.id, policy.document_predicate(),
                                             Document.is_current.is_(True)))
    return [DocumentOut.model_validate(d) for d in rows]


def _ml_patient(db, user, patient_id: int, action: str) -> Patient:
    return _clinical_patient(db, user, patient_id, action)


@router.get("/{patient_id}/risk", response_model=PredictionOut)
def readmission_risk(patient_id: int, db: DB,
                     user: User = Depends(require(Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL))) -> PredictionOut:
    return predict_readmission(db, _ml_patient(db, user, patient_id, "ml.readmission.predict"), user.id)


@router.get("/{patient_id}/length-of-stay", response_model=PredictionOut)
def length_of_stay(patient_id: int, db: DB,
                   user: User = Depends(require(Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL))) -> PredictionOut:
    return predict_length_of_stay(db, _ml_patient(db, user, patient_id, "ml.los.predict"), user.id)


@router.get("/{patient_id}/similar", response_model=SimilarityOut)
def similar(patient_id: int, db: DB, k: int = Query(5, ge=1, le=20),
            user: User = Depends(require(Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL))) -> SimilarityOut:
    p = _ml_patient(db, user, patient_id, "ml.similarity.query")
    return similar_patients(db, policy_for(db, user), p, k=k)


@router.get("/{patient_id}/predictions")
def prediction_history(patient_id: int, db: DB,
                       user: User = Depends(require(Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL))) -> list[dict]:
    p = _ml_patient(db, user, patient_id, "ml.predictions.read")
    rows = db.scalars(select(MLPrediction).where(MLPrediction.patient_id == p.id)
                      .order_by(MLPrediction.created_at.desc()).limit(50))
    return [{"id": r.id, "type": r.prediction_type, "value": r.value, "label": r.label, "created_at": r.created_at,
             "model": r.model_version.model_name, "version": r.model_version.version, "admission_id": r.admission_id}
            for r in rows]
