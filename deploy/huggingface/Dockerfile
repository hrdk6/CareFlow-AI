# CareFlow AI backend for a Hugging Face Docker Space (free CPU tier: 2 vCPU, 16 GB RAM).
#
# The Space holds only this file. Each build downloads the latest `main` from GitHub, so pushing to GitHub and
# restarting the Space ("Settings -> Factory rebuild") deploys new code. Secrets live in the Space settings,
# never in this file. Mirrors backend/Dockerfile, adapted to Spaces: port 7860 and user id 1000.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PORT=7860

# libgomp: OpenMP runtime needed by XGBoost and ONNX Runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

# Source: a remote ADD is re-checked on every build, so a new commit on main invalidates the cache from here on.
ADD https://codeload.github.com/hrdk6/CareFlow-AI/tar.gz/refs/heads/main /tmp/careflow.tar.gz
RUN mkdir -p /src && tar -xzf /tmp/careflow.tar.gz -C /src --strip-components=1 && rm /tmp/careflow.tar.gz \
    && mkdir -p /app/ml/evaluation /app/rag/evaluation \
    && cp -r /src/backend /app/backend \
    && cp /src/ml/__init__.py /app/ml/__init__.py \
    && cp -r /src/ml/artifacts /app/ml/artifacts \
    && cp -r /src/ml/evaluation/reports /app/ml/evaluation/reports \
    && cp -r /src/rag/corpus /app/rag/corpus \
    && cp -r /src/rag/evaluation/results /app/rag/evaluation/results \
    && rm -rf /src

WORKDIR /app/backend
RUN uv sync --frozen --no-dev

# Spaces run the container as user id 1000; storage (uploaded documents) and the model cache must be writable by it.
RUN useradd --create-home --uid 1000 careflow \
    && mkdir -p /app/backend/storage /app/backend/.models \
    && chown -R careflow:careflow /app/backend/storage /app/backend/.models
USER careflow
ENV PATH="/app/backend/.venv/bin:$PATH"

# Bake the embedding + reranker models into the image so the Space starts without downloading them.
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/backend/.models'); \
TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2', cache_dir='/app/backend/.models')"

EXPOSE 7860
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed --if-empty --with-documents && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
