"""Knowledge-base document management and source inspection."""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select

from app.api.deps import DB, policy_for
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import Perm, RoleName
from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.models import Department, Document, DocumentChunk, Patient, User
from app.models.documents import ACCESS_SCOPES, DOC_TYPES
from app.rag.demo_corpus import ingest_demo_corpus
from app.rag.ingestion import create_document, delete_document, process_document
from app.schemas.common import Page
from app.schemas.documents import ChunkOut, DocumentDetailOut, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])
Read = Depends(require(Perm.DOCUMENTS_READ))
Manage = Depends(require(Perm.DOCUMENTS_MANAGE))


def document_out(db, d: Document) -> DocumentOut:
    out = DocumentOut.model_validate(d)
    out.department = db.scalar(select(Department.name).where(Department.id == d.department_id)) if d.department_id else None
    out.patient_mrn = db.scalar(select(Patient.mrn).where(Patient.id == d.patient_id)) if d.patient_id else None
    return out


def _visible(db, user: User, document_id: int) -> Document:
    policy = policy_for(db, user)
    doc = db.scalar(select(Document).where(Document.id == document_id, policy.document_predicate()))
    if doc is None:
        raise NotFoundError("Document not found or not accessible")
    return doc


@router.get("", response_model=Page[DocumentOut])
def list_documents(db: DB, user: User = Read, q: str | None = Query(None, max_length=100),
                   status: str | None = Query(None, pattern="^(uploading|processing|indexed|failed)$"),
                   doc_type: str | None = None, department_id: int | None = None, include_versions: bool = False,
                   limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> Page[DocumentOut]:
    policy = policy_for(db, user)
    stmt = select(Document).where(policy.document_predicate())
    if policy.role != RoleName.ADMIN:
        stmt = stmt.where(Document.status == "indexed", Document.is_current.is_(True))
    elif not include_versions:
        stmt = stmt.where(or_(Document.is_current.is_(True), Document.status != "indexed"))
    if q:
        stmt = stmt.where(or_(Document.title.ilike(f"%{q}%"), Document.doc_key.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Document.status == status)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if department_id:
        stmt = stmt.where(Document.department_id == department_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit).offset(offset))
    return Page(items=[document_out(db, d) for d in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=DocumentOut, status_code=202)
def upload_document(db: DB, background: BackgroundTasks, user: User = Manage,
                    file: Annotated[UploadFile, File()] = ...,
                    title: Annotated[str, Form(min_length=3, max_length=255)] = ...,
                    doc_type: Annotated[str, Form()] = "guideline",
                    access_scope: Annotated[str, Form()] = "clinical",
                    department_id: Annotated[int | None, Form()] = None,
                    patient_id: Annotated[int | None, Form()] = None,
                    doc_key: Annotated[str | None, Form(max_length=128)] = None) -> DocumentOut:
    if doc_type not in DOC_TYPES or access_scope not in ACCESS_SCOPES:
        raise ValidationFailedError(f"doc_type must be one of {DOC_TYPES}; access_scope one of {ACCESS_SCOPES}")
    if patient_id is not None:
        policy_for(db, user).get_patient(patient_id, clinical=True)
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    doc = create_document(db, data=data, filename=file.filename or "upload", title=title, doc_type=doc_type,
                          access_scope=access_scope, department_id=department_id, patient_id=patient_id,
                          uploaded_by=user.id, doc_key=doc_key)
    db.commit()  # the background task uses its own session and must see the row
    background.add_task(process_document, doc.id)
    audit("document.upload", user=user, resource_type="document", resource_id=doc.id, patient_id=patient_id,
          details={"doc_key": doc.doc_key, "version": doc.version, "size": doc.file_size})
    return document_out(db, doc)


@router.post("/demo-corpus", status_code=202)
def load_demo_corpus(db: DB, background: BackgroundTasks, user: User = Manage) -> dict:
    def job() -> None:
        from app.db.session import get_session_factory

        with get_session_factory()() as session:
            ingest_demo_corpus(session, uploaded_by=user.id)

    background.add_task(job)
    audit("document.demo_corpus", user=user)
    return {"status": "accepted", "message": "Demo knowledge base is being ingested; refresh to see progress."}


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: int, db: DB, user: User = Read) -> DocumentDetailOut:
    doc = _visible(db, user, document_id)
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                        .order_by(DocumentChunk.chunk_index)).all()
    audit("document.read", user=user, resource_type="document", resource_id=doc.id, patient_id=doc.patient_id)
    return DocumentDetailOut(**document_out(db, doc).model_dump(), chunks=[ChunkOut.model_validate(c) for c in chunks])


@router.get("/{document_id}/file")
def download_document(document_id: int, db: DB, user: User = Read) -> FileResponse:
    doc = _visible(db, user, document_id)
    path = get_settings().storage_dir / doc.storage_path
    if not path.exists():
        raise NotFoundError("Stored file is missing")
    audit("document.download", user=user, resource_type="document", resource_id=doc.id, patient_id=doc.patient_id)
    return FileResponse(path, media_type=doc.content_type, filename=doc.filename)


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=202)
def reindex(document_id: int, db: DB, background: BackgroundTasks, user: User = Manage) -> DocumentOut:
    doc = _visible(db, user, document_id)
    doc.status = "processing"
    db.commit()
    background.add_task(process_document, doc.id)
    audit("document.reindex", user=user, resource_type="document", resource_id=doc.id)
    return document_out(db, doc)


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: int, db: DB, user: User = Manage) -> Response:
    doc = _visible(db, user, document_id)
    audit("document.delete", user=user, resource_type="document", resource_id=doc.id,
          details={"doc_key": doc.doc_key, "version": doc.version})
    delete_document(db, doc)
    return Response(status_code=204)
