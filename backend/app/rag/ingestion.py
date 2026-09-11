"""Document ingestion: upload -> parse -> clean -> structure -> chunk -> scan -> embed -> index.

Status machine: uploading -> processing -> indexed | failed.
Versioning: re-uploading a document with the same doc_key creates version N+1; it becomes the
current version only after it has been indexed successfully, so retrieval never sees a gap.
"""
import hashlib
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, ValidationFailedError
from app.db.session import get_session_factory
from app.models import Document, DocumentChunk
from app.observability.metrics import COMPONENT_ERRORS
from app.rag.bm25 import bm25_store
from app.rag.chunking import chunk_document
from app.rag.embeddings import get_embedding_service
from app.rag.injection import scan
from app.rag.parsing import SUPPORTED_EXTENSIONS, parse_file
from app.rag.retrieval import embedding_text

logger = logging.getLogger("careflow.rag")
EMBED_BATCH = 32


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:100] or "document"


def _safe_filename(name: str) -> str:
    base = Path(name).name  # strips any directory components (path traversal)
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:120] or "upload"


def create_document(db: Session, *, data: bytes, filename: str, title: str, doc_type: str, access_scope: str,
                    department_id: int | None, patient_id: int | None, uploaded_by: int | None,
                    doc_key: str | None = None, is_synthetic: bool = True) -> Document:
    s = get_settings()
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValidationFailedError(f"Unsupported file type '{ext}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}")
    if not data:
        raise ValidationFailedError("Uploaded file is empty")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ValidationFailedError(f"File exceeds the {s.max_upload_mb} MB limit")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise ValidationFailedError("File content is not a PDF")
    if ext == ".docx" and not data.startswith(b"PK"):
        raise ValidationFailedError("File content is not a DOCX document")
    digest = hashlib.sha256(data).hexdigest()
    key = slugify(doc_key or title)
    current = db.scalar(select(Document).where(Document.doc_key == key, Document.is_current.is_(True)))
    if current is not None and current.sha256 == digest and current.status == "indexed":
        raise ConflictError(f"This exact file is already indexed as '{current.title}' v{current.version}")
    version = (db.scalar(select(func.max(Document.version)).where(Document.doc_key == key)) or 0) + 1
    safe = _safe_filename(filename)
    rel = Path(key) / f"v{version}" / safe
    doc = Document(doc_key=key, title=title.strip()[:255], version=version, is_current=current is None,
                   filename=safe, content_type=SUPPORTED_EXTENSIONS[ext], file_size=len(data), sha256=digest,
                   storage_path=rel.as_posix(), doc_type=doc_type, department_id=department_id,
                   access_scope=access_scope, patient_id=patient_id, status="uploading",
                   uploaded_by_user_id=uploaded_by, is_synthetic=is_synthetic)
    db.add(doc)
    db.flush()
    target = s.storage_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return doc


def process_document(document_id: int) -> str:
    """Run the ingestion pipeline in its own session (background task or CLI). Returns final status."""
    Session = get_session_factory()
    with Session() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return "missing"
        doc.status, doc.error_message = "processing", None
        db.commit()
        t0 = time.perf_counter()
        try:
            s = get_settings()
            parsed = parse_file(s.storage_dir / doc.storage_path)
            chunks = chunk_document(parsed, s.chunk_strategy, s.chunk_max_words, s.chunk_overlap_words)
            if not chunks:
                raise AppError("Document produced no text chunks")
            embedder = get_embedding_service()
            texts = [embedding_text(doc.title, c.section_path, c.text, doc.doc_key) for c in chunks]
            vectors: list[list[float]] = []
            for i in range(0, len(texts), EMBED_BATCH):
                vectors.extend(embedder.embed_documents(texts[i:i + EMBED_BATCH]))
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            flagged = 0
            for chunk, vec in zip(chunks, vectors, strict=True):
                hits = scan(chunk.text)
                flagged += bool(hits)
                db.add(DocumentChunk(
                    document_id=doc.id, chunk_index=chunk.index, text=chunk.text, section_path=chunk.section_path[:512],
                    page_start=chunk.page_start, page_end=chunk.page_end, word_count=chunk.word_count,
                    content_hash=chunk.content_hash, embedding=vec,
                    flags={"injection_suspected": True, "injection_patterns": hits} if hits else {}))
            # Promote this version and retire older ones atomically with the new chunks.
            db.execute(update(Document).where(Document.doc_key == doc.doc_key, Document.id != doc.id)
                       .values(is_current=False))
            doc.is_current = True
            doc.page_count, doc.chunk_count, doc.flagged_chunk_count = parsed.page_count, len(chunks), flagged
            doc.status, doc.indexed_at = "indexed", datetime.now(UTC)
            db.commit()
            bm25_store.invalidate()
            logger.info("document indexed", extra={"fields": {
                "document_id": doc.id, "chunks": len(chunks), "flagged": flagged,
                "ms": round((time.perf_counter() - t0) * 1000)}})
            return "indexed"
        except Exception as exc:
            db.rollback()
            COMPONENT_ERRORS.labels("ingestion").inc()
            logger.exception("document ingestion failed", extra={"fields": {"document_id": document_id}})
            doc = db.get(Document, document_id)
            doc.status = "failed"
            doc.error_message = (exc.message if isinstance(exc, AppError) else "Processing failed")[:512]
            db.commit()
            return "failed"


def delete_document(db: Session, doc: Document) -> None:
    path = get_settings().storage_dir / doc.storage_path
    was_current, key = doc.is_current, doc.doc_key
    db.delete(doc)
    db.flush()
    if was_current:  # fall back to the newest remaining indexed version
        previous = db.scalar(select(Document).where(Document.doc_key == key, Document.status == "indexed")
                             .order_by(Document.version.desc()).limit(1))
        if previous is not None:
            previous.is_current = True
    path.unlink(missing_ok=True)
    bm25_store.invalidate()
