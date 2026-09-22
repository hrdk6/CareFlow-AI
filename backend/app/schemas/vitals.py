"""Bedside observations, their NEWS2 score and the ward board."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai import Citation
from app.schemas.common import ORMModel

Consciousness = Literal["A", "C", "V", "P", "U"]
Risk = Literal["low", "low_medium", "medium", "high"]


class VitalSignsIn(BaseModel):
    """One set of observations. Ranges are the physiologically plausible ones; the score is computed server-side."""

    respiratory_rate: int = Field(ge=0, le=80, description="breaths per minute")
    spo2: int = Field(ge=50, le=100, description="oxygen saturation, %")
    spo2_scale: Literal[1, 2] = Field(default=1, description="scale 2 only on a clinician's instruction "
                                                             "(confirmed hypercapnic respiratory failure)")
    on_oxygen: bool = False
    systolic_bp: int = Field(ge=40, le=300)
    diastolic_bp: int | None = Field(default=None, ge=20, le=200)
    heart_rate: int = Field(ge=20, le=250)
    temperature: float = Field(ge=30, le=45, description="degrees Celsius")
    consciousness: Consciousness = "A"
    recorded_at: datetime | None = None  # defaults to now
    notes: str | None = Field(default=None, max_length=500)


class News2Out(BaseModel):
    score: int
    risk: Risk
    label: str
    parameters: dict[str, int]  # points per parameter
    single_parameter_3: bool  # a 3 in any one parameter triggers a ward-based response on its own
    response: str
    monitoring: str
    due_within_hours: float
    triggers: list[str] = []  # the hospital's rapid-response criteria that apply
    applies: bool = True  # False for a patient the score is not validated for (under 16)
    note: str | None = None


class VitalSignsOut(ORMModel):
    id: int
    patient_id: int
    admission_id: int | None
    recorded_at: datetime
    recorded_by: str | None
    respiratory_rate: int
    spo2: int
    spo2_scale: int
    on_oxygen: bool
    systolic_bp: int
    diastolic_bp: int | None
    heart_rate: int
    temperature: float
    consciousness: Consciousness
    news2_score: int
    news2_risk: Risk
    source: str
    notes: str | None
    news2: News2Out


class TrendPoint(BaseModel):
    at: datetime
    score: int


class WardPatient(BaseModel):
    patient_id: int
    mrn: str
    full_name: str
    age: int
    sex: str
    department: str
    ward: str | None
    admitted_at: datetime
    day_of_stay: int
    reason: str
    attending: str | None
    latest: VitalSignsOut | None
    trend: list[TrendPoint] = []
    due_at: datetime | None = None
    overdue_hours: float | None = None  # None when not overdue


class WardBoardOut(BaseModel):
    generated_at: datetime
    patients: list[WardPatient]
    counts: dict[str, int]  # inpatients, by risk band, overdue, rapid_response
    citations: list[Citation] = []  # the policy sections behind the escalation rules
    note: str
