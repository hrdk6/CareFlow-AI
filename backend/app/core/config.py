"""Central configuration. All secrets come from the environment (see .env.example)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"), env_prefix="CAREFLOW_", extra="ignore",
        populate_by_name=True, env_ignore_empty=True,
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

    # --- public demo hardening ---
    # On a shared public demo, one visitor must not be able to lock the others out: the seeded demo accounts
    # keep their password, role and activation, and each user's AI questions are rate limited to protect the
    # free-tier LLM quota. Unset means on in production only.
    demo_protection: bool | None = None
    ai_queries_per_window: int = 30
    ai_query_window_seconds: int = 600

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
    # Readmission explanations: exact TreeSHAP ("shap"), or tree-path attributions ("tree_path") that skip the
    # ~90 MB shap library on 512 MB hosts. Measured against SHAP on the 110 scorable demo patients: same top factor
    # for 82%, same direction for 99% of shown factors, bar sizes within 15% on average. Risk values are identical.
    ml_explainer: Literal["shap", "tree_path"] = "shap"
    # CPU threads for the ONNX embedding/reranker sessions; empty = all cores. 1 suits small shared-CPU instances
    # and trims per-thread buffers.
    model_threads: int | None = None
    retrieval_candidates: int = 30      # per retriever, before fusion
    rerank_candidates: int = 30         # fused candidates sent to the cross-encoder
    context_chunks: int = 6             # chunks that reach the LLM
    rrf_k: int = 60
    chunk_strategy: Literal["structure", "fixed"] = "structure"
    chunk_max_words: int = 220
    chunk_overlap_words: int = 40

    # --- LLM ---
    llm_provider: Literal["anthropic", "openai_compatible", "groq", "gemini", "extractive"] = "extractive"
    # Backup provider used automatically when the primary fails (rate limit, outage, bad key, timeout).
    llm_fallback_provider: Literal["none", "groq", "gemini", "anthropic", "openai_compatible", "extractive"] = "none"
    # Groq cloud. Keys may be given as CAREFLOW_GROQ_API_KEY or the provider's standard GROQ_API_KEY.
    groq_api_key: str = Field(default="", validation_alias=AliasChoices("CAREFLOW_GROQ_API_KEY", "GROQ_API_KEY"))
    groq_model: str = "openai/gpt-oss-120b"
    # Further Groq models tried in order before the cross-provider backup. Each Groq model has its own free-tier
    # tokens-per-minute allowance, so chaining them multiplies capacity. Comma-separated; empty disables.
    groq_fallback_models: str = "qwen/qwen3.8-27b,openai/gpt-oss-20b"
    groq_reasoning_effort: str | None = "low"  # for gpt-oss models (low | medium | high); Qwen runs with none
    groq_max_tokens: int = 2048  # includes the model's reasoning tokens
    # Groq normally answers in 1-3 s; a stalled request is abandoned quickly so the backup can answer.
    groq_timeout_seconds: float = 20.0
    # Google Gemini via its OpenAI-compatible endpoint (free-tier model by default).
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices(
        "CAREFLOW_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = "gemini-2.5-flash"
    gemini_reasoning_effort: str | None = "none"  # 2.5 models: none disables thinking (faster, fewer tokens)
    gemini_max_tokens: int = 2048
    # After a primary failure, send requests straight to the backup for this long (avoids re-hitting a rate limit).
    llm_fallback_cooldown_seconds: float = 30.0
    llm_model: str = ""
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    anthropic_api_key: str = ""
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 1200
    llm_max_tool_rounds: int = 4
    # "auto": the LLM chooses tools for questions the router cannot classify (needs a fast model, e.g. Claude).
    # "off": always use the router's plan and a single synthesis call (recommended for local CPU models).
    llm_tool_calling: Literal["auto", "off"] = "auto"
    # Evidence is trimmed to fit this many characters (~4 chars/token). Local models often run with a 4k-token
    # window and silently truncate longer prompts, which could drop the system rules.
    llm_context_budget_chars: int = 12000
    llm_reasoning_effort: str | None = None  # OpenAI-compatible "reasoning_effort" (e.g. Ollama thinking models)
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    anthropic_refusal_fallbacks: bool = True
    injection_policy: Literal["quarantine", "annotate"] = "quarantine"

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Managed Postgres hosts (Neon, Supabase, Render, Railway) hand out postgres:// or postgresql:// URLs;
        # SQLAlchemy needs the psycopg 3 driver named explicitly.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def demo_protected(self) -> bool:
        return self.environment == "production" if self.demo_protection is None else self.demo_protection

    def validate_runtime(self) -> None:
        if self.environment != "test" and len(self.jwt_secret) < 32:
            raise RuntimeError(
                "CAREFLOW_JWT_SECRET must be set to a random value of at least 32 characters "
                "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
