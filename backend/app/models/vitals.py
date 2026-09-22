"""Bedside observations (vital signs) and their NEWS2 score."""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.clinical import str_enum
from app.models.identity import User


class VitalSigns(Base):
    __tablename__ = "vital_signs"
    __table_args__ = (
        Index("ix_vital_signs_patient_recorded", "patient_id", "recorded_at"),
        # Physiologically plausible ranges: a typo (SpO2 900) is rejected, a sick patient is not.
        CheckConstraint("respiratory_rate BETWEEN 0 AND 80", name="rr_range"),
        CheckConstraint("spo2 BETWEEN 50 AND 100", name="spo2_range"),
        CheckConstraint("spo2_scale IN (1, 2)", name="spo2_scale_values"),
        CheckConstraint("systolic_bp BETWEEN 40 AND 300", name="sbp_range"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="dbp_range"),
        CheckConstraint("heart_rate BETWEEN 20 AND 250", name="hr_range"),
        CheckConstraint("temperature BETWEEN 30 AND 45", name="temp_range"),
        CheckConstraint("news2_score BETWEEN 0 AND 20", name="news2_range"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id", ondelete="SET NULL"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    respiratory_rate: Mapped[int] = mapped_column(Integer)
    spo2: Mapped[int] = mapped_column(Integer)
    spo2_scale: Mapped[int] = mapped_column(SmallInteger, default=1)
    on_oxygen: Mapped[bool] = mapped_column(Boolean, default=False)
    systolic_bp: Mapped[int] = mapped_column(Integer)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer)
    heart_rate: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[float] = mapped_column(Float)
    consciousness: Mapped[str] = mapped_column(str_enum("A", "C", "V", "P", "U", name="consciousness_level"))
    # Stored for sorting and querying; always recomputable from the values above (app.services.news2).
    news2_score: Mapped[int] = mapped_column(Integer)
    news2_risk: Mapped[str] = mapped_column(str_enum("low", "low_medium", "medium", "high", name="news2_risk"))
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | seed
    notes: Mapped[str | None] = mapped_column(Text)

    recorded_by: Mapped[User | None] = relationship(lazy="joined")
