from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class DocumentOut(ORMModel):
    id: int
    doc_key: str
    title: str
    version: int
    is_current: bool
    filename: str
    content_type: str
    file_size: int
    doc_type: str
    department_id: int | None
    department: str | None = None
    access_scope: str
    patient_id: int | None
    patient_mrn: str | None = None
    status: str
    error_message: str | None
    page_count: int | None
    chunk_count: int
    flagged_chunk_count: int
    is_synthetic: bool
    uploaded_by_user_id: int | None
    created_at: datetime
    indexed_at: datetime | None


class ChunkOut(ORMModel):
    id: int
    chunk_index: int
    text: str
    section_path: str
    page_start: int | None
    page_end: int | None
    word_count: int
    flags: dict


class DocumentDetailOut(DocumentOut):
    chunks: list[ChunkOut]


class SourceOut(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    version: int
    doc_type: str
    department: str | None
    page_start: int | None
    page_end: int | None
    section_path: str
    text: str
    flags: dict
    is_synthetic: bool
