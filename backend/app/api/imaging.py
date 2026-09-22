"""Radiology: the reading queue, a patient's studies, the film itself and the radiologist's report."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from app.api.deps import DB, policy_for
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import Perm
from app.core.config import get_settings
from app.core.errors import ValidationFailedError
from app.imaging import dicom
from app.models import User
from app.schemas.imaging import ReportIn, ReportOut, StudyOut, UploadOut, WorklistOut
from app.services import imaging as service

logger = logging.getLogger("careflow.imaging")
router = APIRouter(tags=["imaging"])
Clinical = Depends(require(Perm.PATIENTS_READ_CLINICAL))
MAX_RENDER_SIDE = 2048


@router.get("/imaging/worklist", response_model=WorklistOut)
def worklist(db: DB, user: User = Clinical) -> WorklistOut:
    """Films waiting to be read, for patients this caller may see, most likely to matter first."""
    queue = service.worklist(db, policy_for(db, user))
    audit("imaging.worklist", user=user, details={"waiting": queue.counts["waiting"]})
    return queue


@router.get("/patients/{patient_id}/imaging", response_model=list[StudyOut])
def patient_studies(patient_id: int, db: DB, user: User = Clinical) -> list[StudyOut]:
    patient = policy_for(db, user).get_patient(patient_id, clinical=True)
    audit("imaging.read", user=user, resource_type="patient", resource_id=patient.id, patient_id=patient.id)
    return service.history(db, patient)


@router.post("/patients/{patient_id}/imaging", response_model=UploadOut, status_code=201)
def upload_study(patient_id: int, db: DB, user: User = Depends(require(Perm.CLINICAL_WRITE)),
                 file: Annotated[UploadFile, File()] = ...,
                 indication: Annotated[str | None, Form(max_length=256)] = None,
                 description: Annotated[str | None, Form(max_length=128)] = None) -> UploadOut:
    """Ingest a DICOM study: de-identified before it is stored, then scored if it is a frontal chest film."""
    patient = policy_for(db, user).get_patient(patient_id, clinical=True)
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailedError(f"That file is larger than the {get_settings().max_upload_mb} MB limit")
    study = service.ingest(db, user, patient, data, indication=indication, description=description,
                           score=get_settings().imaging_triage)
    cleaning = study.deidentification
    removed = len(cleaning.get("removed_tags", [])) + len(cleaning.get("blanked_tags", []))
    return UploadOut(
        study=service.study_out(study), removed_tags=removed,
        message=f"Stored as {study.accession}. {removed} identifying tag(s) were removed before the file "
                f"was written to disk." + ("" if study.triage_prediction_id else
                                           " This study was not scored: the triage model covers frontal "
                                           "chest films only."))


@router.get("/imaging/studies/{study_id}", response_model=StudyOut)
def get_study(study_id: int, db: DB, user: User = Clinical) -> StudyOut:
    study = service.get_study(db, policy_for(db, user), study_id)
    audit("imaging.study_read", user=user, resource_type="imaging_study", resource_id=study.id,
          patient_id=study.patient_id, details={"accession": study.accession})
    return service.study_out(study)


@router.get("/imaging/studies/{study_id}/image.png", include_in_schema=False)
def study_image(study_id: int, db: DB, user: User = Clinical,
                center: float | None = Query(default=None, description="VOI window centre"),
                width: float | None = Query(default=None, gt=0, description="VOI window width"),
                invert: bool = False,
                max_side: int = Query(default=1024, ge=64, le=MAX_RENDER_SIDE)) -> Response:
    """The film, windowed server-side. The viewer adjusts window and level on the canvas; this endpoint
    exists so the browser never has to parse DICOM and so every view of a film passes the access policy."""
    study = service.get_study(db, policy_for(db, user), study_id)
    pixels = service.pixels_of(study)
    png = dicom.to_png(pixels, center if center is not None else study.window_center,
                       width if width is not None else study.window_width, invert=invert, max_side=max_side)
    audit("imaging.image_view", user=user, resource_type="imaging_study", resource_id=study.id,
          patient_id=study.patient_id, details={"accession": study.accession, "max_side": max_side})
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "private, max-age=300"})


@router.put("/imaging/studies/{study_id}/report", response_model=ReportOut)
def write_report(study_id: int, body: ReportIn, db: DB,
                 user: User = Depends(require(Perm.CLINICAL_WRITE))) -> ReportOut:
    """Save or sign the radiologist's report. Signing writes it into the medical record."""
    study = service.get_study(db, policy_for(db, user), study_id)
    return service.save_report(db, user, study, body)
