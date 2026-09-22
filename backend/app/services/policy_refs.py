"""Linking a deterministic check to the policy section it implements.

Rules encoded in code (discharge screening, escalation triggers) are only trustworthy if a reader can see the
text they came from, so each check carries the [S#] id of its policy section. The section is looked up directly
rather than retrieved by similarity: the code implements one specific section, and that is the one to show.
The lookup runs through the caller's document access policy, so an unreadable policy simply yields no citation.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.llm.evidence import EvidenceStore
from app.models import Document, DocumentChunk
from app.rag.retrieval import RetrievedChunk


def indexed_document(db: Session, policy: AccessPolicy, doc_key: str) -> Document | None:
    return db.scalar(select(Document).where(Document.doc_key == doc_key, Document.is_current.is_(True),
                                            Document.status == "indexed", policy.document_predicate()))


def section_citations(db: Session, ev: EvidenceStore, doc: Document, sections: dict[str, str]) -> dict[str, str]:
    """{key: lowercase fragment of the section heading} -> {key: [S#] id}. Flagged passages are skipped."""
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                        .order_by(DocumentChunk.chunk_index)).all()
    out: dict[str, str] = {}
    for key, fragment in sections.items():
        chunk = next((c for c in chunks if fragment in c.section_path.lower()), None)
        if chunk is None or (chunk.flags or {}).get("injection_suspected"):
            continue
        out[key] = ev.ref_chunk(RetrievedChunk(
            chunk_id=chunk.id, document_id=doc.id, document_title=doc.title, doc_version=doc.version,
            doc_key=doc.doc_key, doc_type=doc.doc_type, department=None, section_path=chunk.section_path,
            page_start=chunk.page_start, page_end=chunk.page_end, text=chunk.text, flags=chunk.flags or {},
            content_hash=chunk.content_hash))
    return out
