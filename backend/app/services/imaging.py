"""Radiology: ingesting studies, the reading queue, and the radiologist's report.

The order of operations matters and is the same everywhere in CareFlow: the access policy decides which
patients exist for this caller, the file is de-identified before it is stored, the model runs on the
pixels and writes to `ml_predictions`, and only a clinician's signature puts anything in the record.
"""
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.access import AccessPolicy
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ServiceUnavailableError
from app.imaging import dicom, triage
from app.ml.registry import model_version_row
from app.models import Admission, ImagingReport, ImagingStudy, MedicalRecord, MLPrediction, Patient, User
from app.schemas.imaging import (
    DeidentificationOut,
    FindingOut,
    ReportIn,
    ReportOut,
    StudyOut,
    TriageOut,
    WorklistItem,
    WorklistOut,
)

logger = logging.getLogger("careflow.imaging")

WORKLIST_NOTE = ("The queue is ordered by the model's probability that the film shows any finding. It is a "
                 "reading order, not a diagnosis: every film is read, and a film the model does not flag "
                 "has not been cleared.")
RECENTLY_REPORTED_HOURS = 24
CHEST_BODY_PARTS = {"CHEST", "THORAX"}
TRIAGEABLE_MODALITIES = {"DX", "CR"}


def storage_root() -> Path:
    return Path(get_settings().storage_dir) / "imaging"


def _age(patient: Patient, on: datetime | None = None) -> int:
    today = (on or datetime.now(UTC)).date()
    dob = patient.date_of_birth
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def triageable(study: ImagingStudy) -> bool:
    """The heads were fitted on adult frontal chest films; anything else is stored and shown, not scored."""
    return (study.modality in TRIAGEABLE_MODALITIES
            and (study.body_part or "").upper() in CHEST_BODY_PARTS
            and (study.view_position or "").upper() in {"PA", "AP", ""})


# ------------------------------------------------------------------ ingestion
def ingest(db: Session, user: User | None, patient: Patient, data: bytes, *, indication: str | None = None,
           description: str | None = None, source: str = "upload", admission_id: int | None = None,
           score: bool = True) -> ImagingStudy:
    """Take a DICOM file, strip its identity, store it, score it, and attach it to a patient."""
    # One shift per patient, so several films of the same chest keep their intervals while no real date survives.
    shift = 1 + (int(hashlib.sha256(str(patient.id).encode()).hexdigest(), 16) % 364)
    film, cleaned, cleaning = dicom.read(data, shift_days=shift)

    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{film.study_uid}.dcm"
    path.write_bytes(cleaned)

    acquired = datetime.combine(film.acquired_on or datetime.now(UTC).date(),
                                datetime.min.time(), tzinfo=UTC)
    study = ImagingStudy(
        patient_id=patient.id, admission_id=admission_id, accession=f"IMG-{film.study_uid.rsplit('.', 1)[-1][:12]}",
        study_uid=film.study_uid, series_uid=film.series_uid, sop_uid=film.sop_uid, modality=film.modality,
        body_part=film.body_part, view_position=film.view_position,
        description=description or (f"{film.body_part.title()} {film.view_position}".strip()
                                    if film.body_part else None),
        indication=indication, rows=film.rows, columns=film.columns, bits_stored=film.bits_stored,
        window_center=film.window_center, window_width=film.window_width, acquired_at=acquired,
        storage_path=str(path.relative_to(get_settings().storage_dir)).replace("\\", "/"),
        file_bytes=len(cleaned), sha256=hashlib.sha256(cleaned).hexdigest(), source=source,
        deidentification=cleaning, uploaded_by_user_id=user.id if user else None)
    db.add(study)
    db.flush()

    if score and triageable(study):
        try:
            attach_triage(db, study, film.pixels, user_id=user.id if user else None)
        except ServiceUnavailableError as exc:  # no artifact or no backbone on this host: store, do not score
            logger.warning("study %s stored without a triage score: %s", study.accession, exc)
    audit("imaging.ingest", user=user, resource_type="imaging_study", resource_id=study.id,
          patient_id=patient.id, details={"accession": study.accession, "source": source,
                                          "removed_tags": len(cleaning.get("removed_tags", [])),
                                          "bytes": study.file_bytes})
    return study


def attach_triage(db: Session, study: ImagingStudy, pixels, *, user_id: int | None = None) -> MLPrediction:
    """Score a film and keep the result as a normal ML prediction, versioned like every other model."""
    result = triage.score(pixels)
    version = model_version_row(db, result.model_name, result.model_version)
    row = MLPrediction(
        model_version_id=version.id, patient_id=study.patient_id, admission_id=study.admission_id,
        requested_by_user_id=user_id, prediction_type="cxr_triage", value=result.priority_score,
        label=result.priority,
        features={"study_uid": study.study_uid, "view_position": study.view_position,
                  "rows": study.rows, "columns": study.columns, "backbone": result.backbone},
        explanation={"findings": [f.__dict__ for f in result.findings],
                     "operating_point": result.operating_point, "inference_ms": result.inference_ms})
    db.add(row)
    db.flush()
    study.triage_prediction_id = row.id
    db.flush()
    return row


# ------------------------------------------------------------------ reading
def triage_out(prediction: MLPrediction | None) -> TriageOut | None:
    if prediction is None or prediction.prediction_type != "cxr_triage":
        return None
    explanation = prediction.explanation or {}
    meta = prediction.model_version
    return TriageOut(
        priority=prediction.label or "routine", priority_score=round(prediction.value, 4),
        findings=[FindingOut(**f) for f in explanation.get("findings", [])],
        model_name=meta.model_name, model_version=meta.version, trained_at=meta.trained_at.isoformat(),
        backbone=(prediction.features or {}).get("backbone", ""),
        operating_point=explanation.get("operating_point", ""),
        limitations=_limitations(meta),
        disclaimer=triage.DISCLAIMER, scored_at=prediction.created_at,
        inference_ms=explanation.get("inference_ms"))


def _limitations(version) -> list[str]:
    """The model card's limitations live on disk beside the artifact, not in the database."""
    try:
        from app.ml.registry import get_registry

        return get_registry().metadata(version.model_name, version.version).get("limitations", [])
    except Exception:  # a version whose artifact is no longer installed
        return []


def study_out(study: ImagingStudy) -> StudyOut:
    return StudyOut(
        id=study.id, patient_id=study.patient_id, accession=study.accession, study_uid=study.study_uid,
        modality=study.modality, body_part=study.body_part, view_position=study.view_position,
        description=study.description, indication=study.indication, acquired_at=study.acquired_at,
        rows=study.rows, columns=study.columns, bits_stored=study.bits_stored,
        window_center=study.window_center, window_width=study.window_width, source=study.source,
        deidentification=DeidentificationOut(**(study.deidentification or {})),
        triage=triage_out(study.triage), report=report_out(study.report))


def report_out(report: ImagingReport | None) -> ReportOut | None:
    if report is None:
        return None
    return ReportOut(id=report.id, findings=report.findings, impression=report.impression,
                     status=report.status, model_agreement=report.model_agreement,
                     reported_by=report.reported_by.full_name if report.reported_by else None,
                     signed_at=report.signed_at, record_id=report.record_id)


def get_study(db: Session, policy: AccessPolicy, study_id: int) -> ImagingStudy:
    study = db.get(ImagingStudy, study_id)
    if study is None:
        raise NotFoundError("Study not found")
    policy.get_patient(study.patient_id, clinical=True)  # raises 404 for a patient outside the caller's care
    return study


def storage_path(study: ImagingStudy) -> Path:
    return Path(get_settings().storage_dir) / study.storage_path


def pixels_of(study: ImagingStudy):
    path = storage_path(study)
    if not path.exists():
        raise NotFoundError("The image file for this study is missing from storage")
    return dicom.load(path).pixels


def history(db: Session, patient: Patient) -> list[StudyOut]:
    rows = db.scalars(select(ImagingStudy).where(ImagingStudy.patient_id == patient.id)
                      .order_by(ImagingStudy.acquired_at.desc())).unique().all()
    return [study_out(s) for s in rows]


def worklist(db: Session, policy: AccessPolicy) -> WorklistOut:
    """Films waiting to be read, most likely to matter first, for patients this caller may see."""
    now = datetime.now(UTC)
    since = now - timedelta(hours=RECENTLY_REPORTED_HOURS)
    studies = db.scalars(
        select(ImagingStudy).where(ImagingStudy.patient_id.in_(policy.clinical_patient_ids()))
        .order_by(ImagingStudy.acquired_at.desc())).unique().all()
    patients = {p.id: p for p in db.scalars(select(Patient).where(
        Patient.id.in_([s.patient_id for s in studies])))} if studies else {}
    admitted = set(db.scalars(select(Admission.patient_id).where(Admission.status == "admitted")))

    items: list[WorklistItem] = []
    counts = {"waiting": 0, "priority": 0, "elevated": 0, "routine": 0, "not_scored": 0, "reported": 0}
    for study in studies:
        report = study.report
        reported = report is not None and report.status == "final"
        if reported and (report.signed_at or now) < since:
            continue  # a film read yesterday is history, not a queue
        patient = patients.get(study.patient_id)
        if patient is None:
            continue
        scored = triage_out(study.triage)
        if reported:
            counts["reported"] += 1
        else:
            counts["waiting"] += 1
            counts[scored.priority if scored else "not_scored"] += 1
        items.append(WorklistItem(
            study_id=study.id, accession=study.accession, patient_id=patient.id, mrn=patient.mrn,
            full_name=patient.full_name, age=_age(patient, now), sex=patient.sex,
            department=patient.primary_department.name if patient.primary_department else None,
            inpatient=patient.id in admitted, acquired_at=study.acquired_at,
            waiting_hours=round((now - study.acquired_at).total_seconds() / 3600, 1),
            description=study.description, indication=study.indication, view_position=study.view_position,
            priority=scored.priority if scored else None,
            priority_score=scored.priority_score if scored else None,
            # Only what is above the attention cut-off: at 90% sensitivity almost every film is
            # "not ruled out" for something, which is true and useless as a reading-order signal.
            flagged=[f.label for f in (scored.findings if scored else [])
                     if f.priority and f.finding != triage.ANY_FINDING][:4],
            reported=reported, reported_at=report.signed_at if reported else None))

    order = {"priority": 0, "elevated": 1, "routine": 2, None: 3}
    items.sort(key=lambda i: (i.reported, order.get(i.priority, 3), -(i.priority_score or 0), -i.waiting_hours))
    installed = triage.available()
    version = db.scalar(select(MLPrediction).where(MLPrediction.prediction_type == "cxr_triage")
                        .order_by(MLPrediction.created_at.desc()).limit(1))
    return WorklistOut(generated_at=now, items=items, counts=counts, model_available=installed,
                       model_name=triage.MODEL_NAME if installed else None,
                       model_version=version.model_version.version if version else None,
                       note=WORKLIST_NOTE, disclaimer=triage.DISCLAIMER)


# ------------------------------------------------------------------ reporting
def save_report(db: Session, user: User, study: ImagingStudy, body: ReportIn) -> ReportOut:
    """Write or sign the radiologist's report. Signing is what puts it in the medical record."""
    report = study.report
    if report is not None and report.status == "final":
        raise ConflictError("This study already has a signed report")
    if report is None:
        report = ImagingReport(study_id=study.id)
        db.add(report)
    report.findings = body.findings.strip()
    report.impression = body.impression.strip()
    report.model_agreement = body.model_agreement
    report.reported_by_user_id = user.id
    scored = triage_out(study.triage)
    report.model_snapshot = {
        "model": f"{scored.model_name} v{scored.model_version}" if scored else None,
        "priority": scored.priority if scored else None,
        "priority_score": scored.priority_score if scored else None,
        # What the model actually raised, as the reader saw it named: the findings above the attention
        # cut-off. Everything above the rule-out cut-off is "not ruled out", which is most of them.
        "flagged": [f.label for f in (scored.findings if scored else [])
                    if f.priority and f.finding != triage.ANY_FINDING],
    }

    if not body.sign:
        report.status = "draft"
        db.flush()
        audit("imaging.report_draft", user=user, resource_type="imaging_study", resource_id=study.id,
              patient_id=study.patient_id, details={"accession": study.accession})
        db.refresh(report)
        return report_out(report)

    if user.doctor_id is None:
        raise PermissionDeniedError("Only clinicians with a doctor profile can sign a radiology report")
    now = datetime.now(UTC)
    record = MedicalRecord(
        patient_id=study.patient_id, doctor_id=user.doctor_id, admission_id=study.admission_id,
        visit_date=now.date(), record_type="radiology_report",
        chief_complaint=f"{study.description or study.modality} - {study.accession}"[:255],
        symptoms=study.indication, diagnosis_summary=report.impression, notes=report.findings,
        treatment_plan=None,
        # A report is a human document. The provenance says what the model showed the reader and whether
        # they agreed with it - never that the model wrote any of the text, because it did not.
        ai_provenance={"kind": "radiology_triage_shown", "signed_by": user.full_name,
                       "signed_by_user_id": user.id, "signed_at": now.isoformat(),
                       "model_agreement": body.model_agreement,
                       # The FHIR Provenance points at this assessment as a source the reader consulted.
                       "risk_assessment_id": study.triage_prediction_id, **report.model_snapshot})
    db.add(record)
    db.flush()
    report.status, report.signed_at, report.record_id = "final", now, record.id
    db.flush()
    db.refresh(report)
    audit("imaging.report_sign", user=user, resource_type="imaging_study", resource_id=study.id,
          patient_id=study.patient_id, details={"accession": study.accession, "record_id": record.id,
                                                "model_agreement": body.model_agreement})
    return report_out(report)
