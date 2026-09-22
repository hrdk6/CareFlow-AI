"""Discharge co-pilot: the draft a clinician reviews, and what they sign."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai import Citation, PrivacyOut, RecordRef
from app.schemas.clinical import AdmissionOut, DischargeIn, MedicalRecordOut
from app.schemas.vitals import VitalSignsOut

SentenceIssue = str  # "no_source" | "number_not_in_source:<n>"


class DraftSentence(BaseModel):
    text: str  # with its [R#] markers
    citations: list[str] = []
    issues: list[SentenceIssue] = []  # empty when every claim traces to a cited record


class DraftSection(BaseModel):
    key: Literal["presenting_problem", "hospital_course"]
    title: str
    text: str  # the editable text, sentences joined
    sentences: list[DraftSentence]


class DiagnosisLine(BaseModel):
    code: str
    description: str
    role: Literal["primary", "secondary", "comorbidity"]
    ref: str


class InvestigationLine(BaseModel):
    test_code: str
    test_name: str
    unit: str | None
    first: float | None
    last: float | None
    first_at: datetime
    last_at: datetime
    results: int
    worst_flag: Literal["normal", "low", "high", "critical"]
    refs: list[str]


class MedicationLine(BaseModel):
    medication: str
    status: Literal["continued", "changed", "new", "stopped", "held_resumed", "inpatient_only"]
    before: str | None = None  # regimen on admission
    after: str | None = None  # regimen on the discharge list
    reason: str | None = None
    high_alert: bool = False
    drug_class: str
    refs: list[str] = []


class PolicyCheck(BaseModel):
    key: str
    label: str
    status: Literal["met", "not_met", "to_confirm", "unknown", "not_applicable"]
    detail: str
    refs: list[str] = []  # [R#] records and [S#] policy passages


class RiskScreen(BaseModel):
    high_risk: bool
    criteria: list[PolicyCheck]
    model: dict | None = None  # readmission model estimate for this admission, if it could be scored


class DischargeDraftOut(BaseModel):
    draft_id: int
    status: Literal["draft", "signed", "superseded"]
    admission: AdmissionOut
    patient: dict  # id, mrn, name, age, sex
    generated_at: datetime
    generated_by: str  # "groq/openai/gpt-oss-120b" or "template" (no language model)
    sections: list[DraftSection]
    follow_up_plan: str
    diagnoses: list[DiagnosisLine]
    investigations: list[InvestigationLine]
    observations: VitalSignsOut | None = None  # the latest bedside observations, with their NEWS2 score
    medications: list[MedicationLine]
    risk: RiskScreen
    checklist: list[PolicyCheck]
    record_refs: list[RecordRef]
    citations: list[Citation]
    warnings: list[str] = []
    privacy: PrivacyOut | None = None
    stage_ms: dict = {}
    disclaimer: str


class DischargeSignIn(BaseModel):
    draft_id: int
    presenting_problem: str = Field(min_length=3, max_length=6000)
    hospital_course: str = Field(min_length=3, max_length=12000)
    follow_up_plan: str = Field(min_length=3, max_length=6000)
    # Model sentences flagged as unsupported that are still in the text must be explicitly confirmed.
    confirm_unsupported: bool = False
    discharge: DischargeIn | None = None  # also close the admission, when it is still open


class DischargeSignOut(BaseModel):
    record: MedicalRecordOut
    admission: AdmissionOut
    edited_pct: int  # how much of the generated prose the clinician changed
