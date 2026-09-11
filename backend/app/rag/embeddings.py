"""EmbeddingService abstraction. Nothing outside app.rag calls a model library directly.

- FastEmbedService: ONNX-runtime sentence embeddings (default BAAI/bge-small-en-v1.5, 384-d).
  Chosen over sentence-transformers/PyTorch: same model quality, ~10x smaller runtime, CPU-friendly.
  BGE uses asymmetric encoding - queries get an instruction prefix (fastembed's query_embed).
- HashingEmbeddingService: deterministic feature hashing, no model download. Used by the test-suite
  and as an explicit offline mode; it captures lexical overlap only (documented, never silent).
"""
import hashlib
import logging
import math
import re
import threading
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.observability.metrics import COMPONENT_ERRORS

logger = logging.getLogger("careflow.rag")


class EmbeddingError(ServiceUnavailableError):
    code = "embedding_unavailable"


class EmbeddingService(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedService:
    def __init__(self, model_name: str, dim: int, cache_dir: str, batch_size: int = 32):
        self.name = model_name
        self.dim = dim
        self._cache_dir = cache_dir
        self._batch = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._model is None:
                try:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(self.name, cache_dir=self._cache_dir)
                except Exception as exc:
                    COMPONENT_ERRORS.labels("embedding").inc()
                    logger.exception("embedding model load failed")
                    raise EmbeddingError(f"Embedding model '{self.name}' could not be loaded") from exc
            return self._model

    def _check(self, vectors: list[list[float]]) -> list[list[float]]:
        if vectors and len(vectors[0]) != self.dim:
            raise EmbeddingError(f"Model returned {len(vectors[0])}-d vectors, configured dim is {self.dim}")
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get()
        try:
            return self._check([v.tolist() for v in model.passage_embed(texts, batch_size=self._batch)])
        except EmbeddingError:
            raise
        except Exception as exc:
            COMPONENT_ERRORS.labels("embedding").inc()
            raise EmbeddingError("Embedding generation failed") from exc

    def embed_query(self, text: str) -> list[float]:
        model = self._get()
        try:
            return self._check([v.tolist() for v in model.query_embed([text])])[0]
        except EmbeddingError:
            raise
        except Exception as exc:
            COMPONENT_ERRORS.labels("embedding").inc()
            raise EmbeddingError("Query embedding failed") from exc


_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbeddingService:
    """Signed feature hashing of unigrams + bigrams, L2-normalised."""

    def __init__(self, dim: int):
        self.name = f"hashing-{dim}"
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        tokens = _TOKEN.findall(text.lower())
        feats = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        vec = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    s = get_settings()
    if s.embedding_provider == "hashing":
        return HashingEmbeddingService(s.embedding_dim)
    return FastEmbedService(s.embedding_model, s.embedding_dim, str(s.model_cache_dir))
