# CareFlow AI backend, at the repository root for hosts that expect ./Dockerfile. Keep in sync with backend/Dockerfile.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    MALLOC_ARENA_MAX=2

# MALLOC_ARENA_MAX=2 stops glibc giving every worker thread its own heap, which inflates memory on small hosts.
# libgomp: OpenMP runtime needed by XGBoost and ONNX Runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Versioned model artifacts, evaluation reports and the synthetic knowledge base.
COPY ml/__init__.py /app/ml/__init__.py
COPY ml/artifacts /app/ml/artifacts
COPY ml/data/demo_studies /app/ml/data/demo_studies
COPY ml/evaluation/reports /app/ml/evaluation/reports
COPY rag/corpus /app/rag/corpus
COPY rag/evaluation/results /app/rag/evaluation/results

RUN useradd --create-home --uid 10001 careflow \
    && mkdir -p /app/backend/storage /app/backend/.models \
    && chown -R careflow:careflow /app/backend/storage /app/backend/.models
USER careflow
ENV PATH="/app/backend/.venv/bin:$PATH"

# Bake the embedding + reranker models into the image so containers start offline.
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/backend/.models'); \
TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2', cache_dir='/app/backend/.models')"

# ... and the image backbone the chest radiograph triage heads sit on, for the same reason.
RUN python -c "from app.imaging.backbone import prepared_path; print(prepared_path())"

# Hosts such as Render and Railway assign the port through $PORT; 8000 otherwise.
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed --if-empty --with-documents && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
