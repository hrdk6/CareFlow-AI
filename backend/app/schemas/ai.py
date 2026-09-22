from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.ml import PredictionOut, SimilarityOut


class AIQueryIn(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    patient_id: int | None = Field(default=None, description="Patient in context (e.g. the open profile)")


class Citation(BaseModel):
    id: str  # "S1"
    chunk_id: int
    document_id: int
    document_title: str
    version: int
    page_start: int | None
    page_end: int | None
    section_path: str
    excerpt: str
    retrieval: dict  # {"vector_rank":..,"bm25_rank":..,"rrf":..,"rerank_score":..}


class RecordRef(BaseModel):
    id: str  # "R3"
    source_type: str  # medical_record | lab_report | prescription | admission | diagnosis | appointment
    source_id: int
    label: str
    date: str | None = None


class ToolCallOut(BaseModel):
    name: str
    arguments: dict
    status: str  # ok | denied | error | not_found
    summary: str
    ms: float | None = None


class PrivacyOut(BaseModel):
    """What left the server for the language model. Never the replaced values themselves."""

    applied: bool  # identifiers were replaced with placeholders before sending
    destination: str | None = None  # provider that received the request, e.g. "groq"
    replaced: dict[str, int] = {}  # distinct identifiers replaced, by kind (patient_name, mrn, phone, ...)
    total: int = 0
    preview: str | None = None  # the request content exactly as sent (returned once, never stored)
    name_model: bool = False  # the named-entity pass ran as well as the dictionary


class AIResponse(BaseModel):
    answer: str
    route: list[str]
    routing_method: str
    intents: list[str]
    patient_id: int | None
    citations: list[Citation] = []
    record_refs: list[RecordRef] = []
    predictions: list[PredictionOut] = []
    similarity: SimilarityOut | None = None
    tool_calls: list[ToolCallOut] = []
    warnings: list[str] = []
    limitations: list[str] = []
    insufficient_context: bool = False
    privacy: PrivacyOut | None = None  # None when no language model was called
    provider: str
    model: str | None
    stage_ms: dict = {}
    retrieval: dict = {}
    request_id: str | None = None
    created_at: datetime
    disclaimer: str
