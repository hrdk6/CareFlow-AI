"""Prometheus metrics and a per-request stage timer for AI pipelines."""
import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

HTTP_LATENCY = Histogram(
    "careflow_http_request_seconds", "HTTP request latency", ["method", "route", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
AI_STAGE_LATENCY = Histogram(
    "careflow_ai_stage_seconds", "AI pipeline stage latency", ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
ML_INFERENCE_LATENCY = Histogram(
    "careflow_ml_inference_seconds", "Model inference latency", ["model"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
)
RETRIEVED_CHUNKS = Histogram(
    "careflow_rag_context_chunks", "Chunks passed to the answer stage", buckets=(0, 1, 2, 4, 6, 8, 10, 20)
)
LLM_TOKENS = Counter("careflow_llm_tokens_total", "LLM tokens", ["provider", "kind"])
AI_QUERIES = Counter("careflow_ai_queries_total", "AI queries by route and status", ["route", "status"])
COMPONENT_ERRORS = Counter("careflow_component_errors_total", "Degraded/failed components", ["component"])


class StageTimer:
    """Collects wall-clock milliseconds per named stage and mirrors them to Prometheus."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self.stages[name] = round(self.stages.get(name, 0.0) + elapsed * 1000, 2)
            AI_STAGE_LATENCY.labels(name).observe(elapsed)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)
