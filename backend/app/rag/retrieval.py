"""Authorization-aware hybrid retrieval.

    query -> [vector search (pgvector HNSW, cosine)]  \
                                                        -> RRF fusion -> dedupe -> cross-encoder -> top-k
    query -> [BM25 keyword search (in-memory index)]  /

Both retrievers only ever see chunks the user may read: the access predicate and metadata filters
are part of the SQL that selects candidates, so unauthorized text is never scored, reranked or sent
to the LLM. Reciprocal Rank Fusion is used because cosine similarities and BM25 scores live on
incomparable scales; RRF combines ranks, not scores: rrf(d) = sum_r 1 / (k + rank_r(d)).
"""
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.core.config import Settings, get_settings
from app.models import Department, Document, DocumentChunk
from app.observability.metrics import COMPONENT_ERRORS, RETRIEVED_CHUNKS
from app.rag.bm25 import bm25_store
from app.rag.embeddings import EmbeddingError, EmbeddingService, get_embedding_service
from app.rag.reranking import Reranker, RerankerError, get_reranker

logger = logging.getLogger("careflow.rag")

MODES = ("vector", "keyword", "hybrid", "hybrid_rerank")


@dataclass
class RetrievalFilters:
    department_id: int | None = None
    doc_types: list[str] | None = None
    patient_id: int | None = None
    document_ids: list[int] | None = None


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    doc_version: int
    doc_key: str
    doc_type: str
    department: str | None
    section_path: str
    page_start: int | None
    page_end: int | None
    text: str
    flags: dict
    content_hash: str
    vector_rank: int | None = None
    vector_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None

    @property
    def rerank_text(self) -> str:
        return f"{self.document_title} ({self.doc_key.upper()}). {self.section_path}. {self.text}"

    def retrieval_info(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in {
            "vector_rank": self.vector_rank, "vector_score": self.vector_score, "bm25_rank": self.bm25_rank,
            "bm25_score": self.bm25_score, "rrf_score": self.rrf_score, "rerank_score": self.rerank_score}.items()}


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    mode: str
    vector_candidates: int = 0
    keyword_candidates: int = 0
    fused_candidates: int = 0
    reranked: bool = False
    reranker: str | None = None
    degraded: list[str] = field(default_factory=list)
    stage_ms: dict = field(default_factory=dict)
    below_threshold: int = 0

    def summary(self) -> dict:
        return {"mode": self.mode, "vector_candidates": self.vector_candidates,
                "keyword_candidates": self.keyword_candidates, "fused_candidates": self.fused_candidates,
                "reranked": self.reranked, "reranker": self.reranker, "returned": len(self.chunks),
                "dropped_below_relevance_threshold": self.below_threshold, "degraded": self.degraded}


def embedding_text(title: str, section: str, body: str, doc_key: str = "") -> str:
    """Contextual chunk header: title, document code and section path give short chunks their missing
    context (a chunk about abbreviating "units" does not itself mention MED-POL-004)."""
    head = f"{title} ({doc_key.upper()})" if doc_key else title
    return f"{head}\n{section}\n{body}" if section else f"{head}\n{body}"


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


class HybridRetriever:
    MIN_RERANK_SCORE = -4.0  # ms-marco cross-encoder logit; below this a passage is judged irrelevant

    def __init__(self, db: Session, policy: AccessPolicy, *, embedder: EmbeddingService | None = None,
                 reranker: Reranker | None = None, settings: Settings | None = None):
        self.db = db
        self.policy = policy
        self.embedder = embedder or get_embedding_service()
        self.reranker = reranker or get_reranker()
        self.s = settings or get_settings()

    # ------------------------------------------------------------------ filtering
    def _where(self, filters: RetrievalFilters):
        conds = [Document.status == "indexed", Document.is_current.is_(True), self.policy.document_predicate()]
        if filters.department_id is not None:
            conds.append((Document.department_id == filters.department_id) | Document.department_id.is_(None))
        if filters.doc_types:
            conds.append(Document.doc_type.in_(filters.doc_types))
        if filters.patient_id is not None:
            conds.append((Document.patient_id == filters.patient_id) | Document.patient_id.is_(None))
        if filters.document_ids:
            conds.append(Document.id.in_(filters.document_ids))
        return and_(*conds)

    # ------------------------------------------------------------------ retrievers
    def vector_search(self, query: str, filters: RetrievalFilters, k: int) -> list[tuple[int, float]]:
        qvec = self.embedder.embed_query(query)
        self.db.execute(text(f"SET LOCAL hnsw.ef_search = {max(100, k * 4)}"))
        distance = DocumentChunk.embedding.cosine_distance(qvec)
        rows = self.db.execute(
            select(DocumentChunk.id, distance.label("d")).join(Document, Document.id == DocumentChunk.document_id)
            .where(self._where(filters)).order_by(distance).limit(k)).all()
        return [(cid, 1.0 - float(d)) for cid, d in rows]

    def _corpus_signature(self) -> tuple:
        return tuple(self.db.execute(
            select(func.count(DocumentChunk.id), func.max(DocumentChunk.id), func.max(Document.updated_at))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.status == "indexed", Document.is_current.is_(True))).one())

    def _corpus_loader(self):
        rows = self.db.execute(
            select(DocumentChunk.id, Document.title, Document.doc_key, DocumentChunk.section_path, DocumentChunk.text)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.status == "indexed", Document.is_current.is_(True))).all()
        return [(cid, f"{title} {key} {section} {body}") for cid, title, key, section, body in rows]

    def keyword_search(self, query: str, filters: RetrievalFilters, k: int) -> list[tuple[int, float]]:
        allowed = set(self.db.scalars(
            select(DocumentChunk.id).join(Document, Document.id == DocumentChunk.document_id)
            .where(self._where(filters))))
        if not allowed:
            return []
        index = bm25_store.get(self._corpus_signature(), self._corpus_loader)
        return index.search(query, k, allowed)

    def _load(self, ids: list[int]) -> dict[int, RetrievedChunk]:
        if not ids:
            return {}
        rows = self.db.execute(
            select(DocumentChunk, Document, Department.name)
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(Department, Department.id == Document.department_id)
            .where(DocumentChunk.id.in_(ids), self._where(RetrievalFilters()))).all()
        return {c.id: RetrievedChunk(
            chunk_id=c.id, document_id=d.id, document_title=d.title, doc_version=d.version, doc_key=d.doc_key,
            doc_type=d.doc_type,
            department=dept, section_path=c.section_path, page_start=c.page_start, page_end=c.page_end,
            text=c.text, flags=c.flags or {}, content_hash=c.content_hash) for c, d, dept in rows}

    # ------------------------------------------------------------------ pipeline
    def retrieve(self, query: str, filters: RetrievalFilters | None = None, *, mode: str = "hybrid_rerank",
                 top_k: int | None = None) -> RetrievalResult:
        if mode not in MODES:
            raise ValueError(f"unknown retrieval mode {mode}")
        filters = filters or RetrievalFilters()
        top_k = top_k or self.s.context_chunks
        result = RetrievalResult(chunks=[], mode=mode)
        n = self.s.retrieval_candidates

        vector: list[tuple[int, float]] = []
        keyword: list[tuple[int, float]] = []
        if mode in ("vector", "hybrid", "hybrid_rerank"):
            t0 = time.perf_counter()
            try:
                vector = self.vector_search(query, filters, n)
            except EmbeddingError:
                COMPONENT_ERRORS.labels("vector_search").inc()
                result.degraded.append("vector_search_unavailable")
                logger.warning("vector search unavailable - continuing with keyword search")
                if mode == "vector":
                    raise
            except Exception:
                COMPONENT_ERRORS.labels("vector_search").inc()
                logger.exception("vector search failed")
                self.db.rollback()
                result.degraded.append("vector_search_failed")
            result.stage_ms["vector_search"] = round((time.perf_counter() - t0) * 1000, 2)
        if mode in ("keyword", "hybrid", "hybrid_rerank"):
            t0 = time.perf_counter()
            try:
                keyword = self.keyword_search(query, filters, n)
            except Exception:
                COMPONENT_ERRORS.labels("keyword_search").inc()
                logger.exception("keyword search failed")
                result.degraded.append("keyword_search_failed")
            result.stage_ms["keyword_search"] = round((time.perf_counter() - t0) * 1000, 2)
        result.vector_candidates, result.keyword_candidates = len(vector), len(keyword)

        t0 = time.perf_counter()
        fused = rrf_fuse([[cid for cid, _ in vector], [cid for cid, _ in keyword]], k=self.s.rrf_k)
        order = sorted(fused, key=lambda cid: -fused[cid])[: self.s.rerank_candidates]
        loaded = self._load(order)
        vrank = {cid: (i + 1, s) for i, (cid, s) in enumerate(vector)}
        krank = {cid: (i + 1, s) for i, (cid, s) in enumerate(keyword)}
        candidates, seen_hashes = [], set()
        for cid in order:
            chunk = loaded.get(cid)
            if chunk is None or chunk.content_hash in seen_hashes:  # dedupe identical passages across versions
                continue
            seen_hashes.add(chunk.content_hash)
            chunk.rrf_score = fused[cid]
            if cid in vrank:
                chunk.vector_rank, chunk.vector_score = vrank[cid]
            if cid in krank:
                chunk.bm25_rank, chunk.bm25_score = krank[cid]
            candidates.append(chunk)
        result.fused_candidates = len(candidates)
        result.stage_ms["fusion"] = round((time.perf_counter() - t0) * 1000, 2)

        if mode == "hybrid_rerank" and candidates:
            t0 = time.perf_counter()
            try:
                scores = self.reranker.score(query, [c.rerank_text for c in candidates])
                for c, s in zip(candidates, scores, strict=True):
                    c.rerank_score = s
                candidates.sort(key=lambda c: -(c.rerank_score or 0.0))
                result.reranked, result.reranker = True, self.reranker.name
                if self.reranker.name != "none":
                    kept = [c for c in candidates if (c.rerank_score or 0) >= self.MIN_RERANK_SCORE]
                    result.below_threshold = len(candidates) - len(kept)
                    candidates = kept
            except RerankerError:
                result.degraded.append("reranker_unavailable")
                logger.warning("reranker unavailable - using fused order")
            result.stage_ms["rerank"] = round((time.perf_counter() - t0) * 1000, 2)
            if not result.reranked or self.reranker.name == "none":
                # Without a cross-encoder there is no relevance judgement: vector search always returns
                # *something*. Require lexical evidence so unanswerable questions yield "insufficient context".
                kept = [c for c in candidates if c.bm25_rank is not None]
                result.below_threshold = len(candidates) - len(kept)
                candidates = kept
        result.chunks = candidates[:top_k]
        RETRIEVED_CHUNKS.observe(len(result.chunks))
        return result
