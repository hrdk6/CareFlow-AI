"""AI assistant endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DB, policy_for
from app.audit.service import audit
from app.auth.dependencies import get_current_user, require
from app.auth.rbac import Perm
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.llm.orchestrator import AIOrchestrator
from app.llm.providers import get_llm_provider
from app.models import Department, Document, DocumentChunk, User
from app.schemas.ai import AIQueryIn, AIResponse
from app.schemas.documents import SourceOut

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=AIResponse)
def ai_query(body: AIQueryIn, db: DB, user: User = Depends(require(Perm.AI_QUERY))) -> AIResponse:
    return AIOrchestrator(db, user).run(body)


@router.get("/sources/{chunk_id}", response_model=SourceOut)
def get_source(chunk_id: int, db: DB, user: User = Depends(require(Perm.DOCUMENTS_READ))) -> SourceOut:
    """Inspect a cited passage. The same access predicate as retrieval applies."""
    row = db.execute(select(DocumentChunk, Document, Department.name)
                     .join(Document, Document.id == DocumentChunk.document_id)
                     .outerjoin(Department, Department.id == Document.department_id)
                     .where(DocumentChunk.id == chunk_id, policy_for(db, user).document_predicate())).first()
    if row is None:
        raise NotFoundError("Source not found or not accessible")
    chunk, doc, dept = row
    audit("document.source_view", user=user, resource_type="document_chunk", resource_id=chunk.id,
          patient_id=doc.patient_id)
    return SourceOut(chunk_id=chunk.id, document_id=doc.id, document_title=doc.title, version=doc.version,
                     doc_type=doc.doc_type, department=dept, page_start=chunk.page_start, page_end=chunk.page_end,
                     section_path=chunk.section_path, text=chunk.text, flags=chunk.flags or {},
                     is_synthetic=doc.is_synthetic)


def _probe(provider) -> bool | None:
    """Lists models (no tokens spent) to check the endpoint and key. None = not probed (Anthropic, extractive)."""
    probe = getattr(provider, "probe", None)
    return probe() if probe else None


@router.get("/status")
def ai_status(user: User = Depends(get_current_user)) -> dict:
    s = get_settings()
    provider = get_llm_provider()
    chain = getattr(provider, "providers", [provider])
    probes: dict = {}  # Groq models share one endpoint and key: probe it once

    def reachable(p) -> bool | None:
        key = (getattr(p, "base_url", p.name), getattr(p, "api_key", ""))
        if key not in probes:
            probes[key] = _probe(p)
        return probes[key]

    fallbacks = [{"provider": p.name, "model": p.model, "reachable": reachable(p)} for p in chain[1:]]
    return {"provider": provider.name, "model": getattr(provider, "model", None), "reachable": reachable(chain[0]),
            "fallbacks": fallbacks, "tool_calling": provider.supports_tools, "embedding_model": s.embedding_model if
            s.embedding_provider == "fastembed" else "hashing", "reranker": s.reranker_model if
            s.reranker_provider == "cross_encoder" else "none", "injection_policy": s.injection_policy}
