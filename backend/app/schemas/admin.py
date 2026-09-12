from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel

RoleLiteral = Literal["ADMIN", "DOCTOR", "NURSE", "RECEPTIONIST"]


class UserAdminOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    doctor_id: int | None
    department_id: int | None
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=12, max_length=256)
    role: RoleLiteral
    doctor_id: int | None = None
    department_id: int | None = None


class UserUpdate(BaseModel):
    role: RoleLiteral | None = None
    is_active: bool | None = None
    department_id: int | None = None
    doctor_id: int | None = None  # set when promoting to DOCTOR; cleared automatically for other roles


class CareAssignmentIn(BaseModel):
    patient_id: int
    user_id: int
    care_role: Literal["attending", "consulting", "nurse"]


class RoleOut(BaseModel):
    name: str
    description: str
    permissions: list[str]


class AuditLogOut(ORMModel):
    id: int
    occurred_at: datetime
    user_id: int | None
    user_role: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    patient_id: int | None
    outcome: str
    ip_address: str | None
    request_id: str | None
    details: dict


class AITraceOut(ORMModel):
    id: int
    created_at: datetime
    user_id: int | None
    request_id: str | None
    query_length: int
    route: str
    routing_method: str
    provider: str
    llm_model: str | None
    status: str
    error_code: str | None
    total_ms: float
    stage_ms: dict
    retrieved_chunk_ids: list
    cited_source_ids: list
    tool_calls: list
    model_versions: list
    prompt_tokens: int | None
    completion_tokens: int | None
