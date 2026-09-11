"""Model registry, persisted predictions and patient representations for similarity."""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SIMILARITY_DIM = 32  # must equal len(app.ml.similarity.FEATURE_NAMES); checked at startup


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_name", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    task: Mapped[str] = mapped_column(String(32))  # classification | regression | similarity
    algorithm: Mapped[str] = mapped_column(String(64))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dataset_name: Mapped[str] = mapped_column(String(128))
    dataset_version: Mapped[str] = mapped_column(String(64))
    feature_config: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (Index("ix_ml_predictions_patient_created", "patient_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    prediction_type: Mapped[str] = mapped_column(String(32))  # readmission_30d | length_of_stay
    value: Mapped[float] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(String(32))
    features: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    model_version: Mapped[ModelVersion] = relationship(lazy="joined")


class PatientEmbedding(Base):
    """Structured-feature representation of a patient used for similarity search."""

    __tablename__ = "patient_embeddings"
    __table_args__ = (
        Index(
            "ix_patient_embeddings_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    representation_version: Mapped[str] = mapped_column(String(32))
    vector: Mapped[list[float]] = mapped_column(Vector(SIMILARITY_DIM))
    features: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
