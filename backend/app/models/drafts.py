"""AI-generated drafts awaiting clinician review. Nothing reaches the medical record until a clinician signs."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.clinical import str_enum


class AIDraft(Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (Index("ix_ai_drafts_admission_status", "admission_id", "status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(str_enum("discharge_summary", name="ai_draft_kind"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    status: Mapped[str] = mapped_column(str_enum("draft", "signed", "superseded", name="ai_draft_status"),
                                        default="draft")
    generated_by: Mapped[str] = mapped_column(String(128))  # "groq/openai/gpt-oss-120b" or "template"
    # The full draft as shown to the clinician (sections, sentence flags, reconciliation, checks, sources).
    content: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    signed_record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
