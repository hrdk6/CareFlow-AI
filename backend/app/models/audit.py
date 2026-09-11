"""Audit trail and AI query traces. Neither stores clinical free text or raw queries."""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. patient.read, ai.query
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    patient_id: Mapped[int | None] = mapped_column(Integer, index=True)  # reference only, no PHI
    outcome: Mapped[str] = mapped_column(String(16))  # success | denied | error
    ip_address: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class AIQueryTrace(Base):
    __tablename__ = "ai_query_traces"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_id: Mapped[str | None] = mapped_column(String(64))
    query_hash: Mapped[str] = mapped_column(String(64))
    query_length: Mapped[int] = mapped_column(Integer)
    route: Mapped[str] = mapped_column(String(64), index=True)
    routing_method: Mapped[str] = mapped_column(String(16))  # deterministic | llm
    provider: Mapped[str] = mapped_column(String(32))
    llm_model: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    total_ms: Mapped[float] = mapped_column(Float)
    stage_ms: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    cited_source_ids: Mapped[list] = mapped_column(JSON, default=list)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    model_versions: Mapped[list] = mapped_column(JSON, default=list)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
