"""Radiology: de-identified studies, what the triage model said, and the radiologist's report."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.clinical import str_enum
from app.models.identity import User
from app.models.ml import MLPrediction


class ImagingStudy(Base):
    """One radiograph, stored as DICOM. The file holds no identifiers: this row is the only link to a
    patient, and it is behind the same row-level access policy as the rest of the record."""

    __tablename__ = "imaging_studies"
    __table_args__ = (Index("ix_imaging_studies_patient_acquired", "patient_id", "acquired_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"))
    accession: Mapped[str] = mapped_column(String(24), unique=True)   # CareFlow's own, never the sender's
    study_uid: Mapped[str] = mapped_column(String(80), unique=True)
    series_uid: Mapped[str] = mapped_column(String(80))
    sop_uid: Mapped[str] = mapped_column(String(80))
    modality: Mapped[str] = mapped_column(String(8), default="DX")
    body_part: Mapped[str | None] = mapped_column(String(32))
    view_position: Mapped[str | None] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(String(128))
    indication: Mapped[str | None] = mapped_column(String(256))       # why the film was requested
    rows: Mapped[int] = mapped_column(Integer)
    columns: Mapped[int] = mapped_column(Integer)
    bits_stored: Mapped[int] = mapped_column(Integer, default=8)
    window_center: Mapped[float] = mapped_column(Float)
    window_width: Mapped[float] = mapped_column(Float)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    storage_path: Mapped[str] = mapped_column(String(512))
    file_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), default="upload")  # upload | seed
    # What was stripped on ingest, so the record can show it rather than just promise it.
    deidentification: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    triage_prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_predictions.id", ondelete="SET NULL"))

    triage: Mapped[MLPrediction | None] = relationship(lazy="joined")
    report: Mapped["ImagingReport | None"] = relationship(back_populates="study", lazy="joined",
                                                          cascade="all, delete-orphan", uselist=False)


class ImagingReport(Base):
    """The radiologist's report. The model never writes here: a report exists because a clinician wrote
    and signed it, and what the model had said at that moment is kept beside it."""

    __tablename__ = "imaging_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("imaging_studies.id", ondelete="CASCADE"), unique=True)
    findings: Mapped[str] = mapped_column(Text)
    impression: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(str_enum("draft", "final", name="imaging_report_status"),
                                        default="draft")
    # The reader's verdict on the model, captured at sign-off: it is the only honest source of "was the
    # model right?" once a film is no longer a test-set film.
    model_agreement: Mapped[str | None] = mapped_column(
        str_enum("agreed", "partly", "disagreed", "not_used", name="imaging_model_agreement"))
    model_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # what was on screen when it was signed
    reported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"))

    study: Mapped[ImagingStudy] = relationship(back_populates="report")
    reported_by: Mapped[User | None] = relationship(lazy="joined")
