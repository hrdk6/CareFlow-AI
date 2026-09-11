"""Central configuration. All secrets come from the environment (see .env.example)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"), env_prefix="CAREFLOW_", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "CareFlow AI"
    log_level: str = "INFO"

    # --- database ---
    database_url: str = "postgresql+psycopg://careflow:careflow@localhost:5432/careflow"
    db_pool_size: int = 10
    db_max_overflow: int = 10

    # --- auth ---
    jwt_secret: str = Field(default="", description="HS256 signing key. Required outside tests.")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- storage ---
    storage_dir: Path = BACKEND_DIR / "storage"
    max_upload_mb: int = 20

    # --- ML ---
    model_dir: Path = REPO_DIR / "ml" / "artifacts"

    # --- embeddings / retrieval ---
    embedding_provider: Literal["fastembed", "hashing"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    model_cache_dir: Path = BACKEND_DIR / ".models"
    reranker_provider: Literal["cross_encoder", "none"] = "cross_encoder"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    retrieval_candidates: int = 30      # per retriever, before fusion
    rerank_candidates: int = 30         # fused candidates sent to the cross-encoder
    context_chunks: int = 6             # chunks that reach the LLM
    rrf_k: int = 60
    chunk_strategy: Literal["structure", "fixed"] = "structure"
    chunk_max_words: int = 220
    chunk_overlap_words: int = 40

    # --- LLM ---
    llm_provider: Literal["anthropic", "openai_compatible", "extractive"] = "extractive"
    llm_model: str = ""
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    anthropic_api_key: str = ""
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 1200
    llm_max_tool_rounds: int = 4
    # Evidence is trimmed to fit this many characters (~4 chars/token). Local models often run with a 4k-token
    # window and silently truncate longer prompts, which could drop the system rules.
    llm_context_budget_chars: int = 12000
    llm_reasoning_effort: str | None = None  # OpenAI-compatible "reasoning_effort" (e.g. Ollama thinking models)
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    anthropic_refusal_fallbacks: bool = True
    injection_policy: Literal["quarantine", "annotate"] = "quarantine"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def validate_runtime(self) -> None:
        if self.environment != "test" and len(self.jwt_secret) < 32:
            raise RuntimeError(
                "CAREFLOW_JWT_SECRET must be set to a random value of at least 32 characters "
                "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
