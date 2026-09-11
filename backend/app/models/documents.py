"""Knowledge-base documents and their retrievable chunks."""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.clinical import str_enum

EMBEDDING_DIM = 384  # must match CAREFLOW_EMBEDDING_DIM; changing it requires a migration + re-index

DOC_STATUSES = ("uploading", "processing", "indexed", "failed")
DOC_TYPES = ("guideline", "policy", "protocol", "procedure", "report", "other")
ACCESS_SCOPES = ("all_staff", "clinical", "admin")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("doc_key", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_key: Mapped[str] = mapped_column(String(128), index=True)  # stable identity across versions
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(512))
    doc_type: Mapped[str] = mapped_column(str_enum(*DOC_TYPES, name="doc_type"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    access_scope: Mapped[str] = mapped_column(str_enum(*ACCESS_SCOPES, name="access_scope"), index=True)
    # Patient-specific documents inherit that patient's access policy.
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(str_enum(*DOC_STATUSES, name="doc_status"), default="uploading", index=True)
    error_message: Mapped[str | None] = mapped_column(String(512))
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    flagged_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    section_path: Mapped[str] = mapped_column(String(512), default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # e.g. {"injection_suspected": true, "injection_patterns": ["override_instructions"]}
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="chunks")
