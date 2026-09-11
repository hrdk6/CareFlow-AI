from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FactorOut(BaseModel):
    feature: str
    label: str
    value: str
    contribution: float
    direction: Literal["up", "down"]
    text: str


class ReferenceAdmission(BaseModel):
    admission_id: int
    admitted_at: datetime
    discharged_at: datetime | None
    status: str
    reason: str
    actual_length_of_stay_days: float | None


class PredictionOut(BaseModel):
    prediction_type: Literal["readmission_30d", "length_of_stay"]
    status: Literal["ok", "not_applicable"]
    reason: str | None = None
    prediction_id: int | None = None
    value: float | None = None
    label: str | None = None
    unit: str | None = None
    threshold: float | None = None
    flagged: bool | None = None
    interval: list[float] | None = None
    model_name: str | None = None
    model_version: str | None = None
    model_algorithm: str | None = None
    trained_at: str | None = None
    predicted_at: datetime | None = None
    reference: ReferenceAdmission | None = None
    features: dict = {}
    missing_features: list[str] = []
    factors: list[FactorOut] = []
    explanation_space: str | None = None
    in_training_population: bool = True
    notes: list[str] = []
    context: dict = {}
    limitations: list[str] = []
    disclaimer: str


class SimilarPatientOut(BaseModel):
    patient_id: int
    mrn: str
    full_name: str
    age: float
    sex: str
    similarity: float
    shared_diagnosis_categories: list[str]
    shared_medication_groups: list[str]
    diagnoses: list[str]
    admissions_2y: int
    mean_los_days: float | None
    last_hba1c: float | None
    last_egfr: float | None


class SimilarityOut(BaseModel):
    patient_id: int
    representation_version: str
    metric: str
    query_profile: dict
    results: list[SimilarPatientOut]
    cohort_patterns: dict
    candidate_scope: str
    disclaimer: str


class ModelCardOut(BaseModel):
    model_name: str
    version: str
    is_active: bool
    task: str
    algorithm: str
    trained_at: str
    dataset: dict
    features: dict
    metrics: dict
    candidates: list[dict]
    global_importance: dict
    leakage_ablation: dict
    limitations: list[str]
    intended_use: str
    extra: dict = {}
