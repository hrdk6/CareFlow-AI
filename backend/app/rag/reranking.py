"""Reranker abstraction.

A bi-encoder (the embedding model) scores query and passage independently - fast enough to search
the whole corpus but blind to fine-grained interactions. A cross-encoder reads (query, passage)
together and is far more precise, but costs one forward pass per pair - so it is applied only to
the ~30 fused candidates, never to the corpus.
"""
import logging
import threading
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.observability.metrics import COMPONENT_ERRORS

logger = logging.getLogger("careflow.rag")


class RerankerError(ServiceUnavailableError):
    code = "reranker_unavailable"


class Reranker(Protocol):
    name: str

    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str, cache_dir: str, batch_size: int = 16):
        self.name = model_name
        self._cache_dir = cache_dir
        self._batch = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._model is None:
                try:
                    from fastembed.rerank.cross_encoder import TextCrossEncoder

                    self._model = TextCrossEncoder(self.name, cache_dir=self._cache_dir)
                except Exception as exc:
                    COMPONENT_ERRORS.labels("reranker").inc()
                    raise RerankerError(f"Reranker '{self.name}' could not be loaded") from exc
            return self._model

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        model = self._get()
        try:
            return [float(s) for s in model.rerank(query, passages, batch_size=self._batch)]
        except Exception as exc:
            COMPONENT_ERRORS.labels("reranker").inc()
            raise RerankerError("Reranking failed") from exc


class NoopReranker:
    """Keeps the fused order (used when reranking is disabled)."""

    name = "none"

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [-float(i) for i in range(len(passages))]


@lru_cache
def get_reranker() -> Reranker:
    s = get_settings()
    if s.reranker_provider == "none":
        return NoopReranker()
    return CrossEncoderReranker(s.reranker_model, str(s.model_cache_dir))
