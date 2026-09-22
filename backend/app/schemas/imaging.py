"""Radiology studies, the triage model's output and the radiologist's report."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

Priority = Literal["routine", "elevated", "priority"]
Agreement = Literal["agreed", "partly", "disagreed", "not_used"]


class FindingOut(BaseModel):
    """One finding the model reports, with the numbers a reader needs to weigh it."""

    finding: str
    label: str
    probability: float
    threshold: float
    flagged: bool
    priority: bool
    roc_auc: float
    roc_auc_ci: list[float]
    sensitivity: float | None
    specificity: float | None
    prevalence: float
    attention: list[list[float]] = []  # class activation map over the film, row-major, 0-1


class TriageOut(BaseModel):
    priority: Priority
    priority_score: float
    findings: list[FindingOut]
    model_name: str
    model_version: str
    trained_at: str
    backbone: str
    operating_point: str
    limitations: list[str]
    disclaimer: str
    scored_at: datetime | None = None
    inference_ms: int | None = None


class DeidentificationOut(BaseModel):
    method: str = ""
    removed_tags: list[str] = []
    blanked_tags: list[str] = []
    date_tags_shifted: list[str] = []
    shift_days: int = 0
    private_tags_removed: bool = False
    uids_regenerated: bool = False


class ReportOut(ORMModel):
    id: int
    findings: str
    impression: str
    status: Literal["draft", "final"]
    model_agreement: Agreement | None
    reported_by: str | None
    signed_at: datetime | None
    record_id: int | None


class StudyOut(ORMModel):
    id: int
    patient_id: int
    accession: str
    study_uid: str
    modality: str
    body_part: str | None
    view_position: str | None
    description: str | None
    indication: str | None
    acquired_at: datetime
    rows: int
    columns: int
    bits_stored: int
    window_center: float
    window_width: float
    source: str
    deidentification: DeidentificationOut
    triage: TriageOut | None = None
    report: ReportOut | None = None


class WorklistItem(BaseModel):
    """A film waiting to be read, as the reading queue shows it."""

    study_id: int
    accession: str
    patient_id: int
    mrn: str
    full_name: str
    age: int
    sex: str
    department: str | None
    inpatient: bool
    acquired_at: datetime
    waiting_hours: float
    description: str | None
    indication: str | None
    view_position: str | None
    priority: Priority | None
    priority_score: float | None
    flagged: list[str] = []          # findings above their attention cut-off, most likely first
    reported: bool
    reported_at: datetime | None = None


class WorklistOut(BaseModel):
    generated_at: datetime
    items: list[WorklistItem]
    counts: dict[str, int]
    model_available: bool
    model_name: str | None = None
    model_version: str | None = None
    note: str
    disclaimer: str


class ReportIn(BaseModel):
    findings: str = Field(min_length=1, max_length=8000)
    impression: str = Field(min_length=1, max_length=4000)
    model_agreement: Agreement = Field(
        description="Whether the reader's own read matched what the model flagged; 'not_used' if the "
                    "model's output was not consulted")
    sign: bool = Field(default=False, description="Sign the report into the medical record")


class UploadOut(BaseModel):
    study: StudyOut
    removed_tags: int
    message: str
