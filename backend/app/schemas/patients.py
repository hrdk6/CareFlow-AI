from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


class Allergy(BaseModel):
    substance: str = Field(min_length=1, max_length=64)
    reaction: str = Field(min_length=1, max_length=64)
    severity: Literal["mild", "moderate", "severe"]


class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    date_of_birth: date
    sex: Literal["F", "M", "X"]
    phone: str | None = Field(default=None, max_length=32, pattern=r"^[0-9+\-() ]{5,32}$")
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    preferred_language: str = Field(default="English", max_length=32)
    blood_type: str | None = Field(default=None, pattern=r"^(A|B|AB|O)[+-]$")
    emergency_contact_name: str | None = Field(default=None, max_length=128)
    emergency_contact_phone: str | None = Field(default=None, max_length=32, pattern=r"^[0-9+\-() ]{5,32}$")
    emergency_contact_relation: str | None = Field(default=None, max_length=32)
    allergies: list[Allergy] = []
    primary_department_id: int | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_in_past(cls, v: date) -> date:
        if v >= date.today() or v.year < 1900:
            raise ValueError("date_of_birth must be in the past and after 1900")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=64)
    last_name: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32, pattern=r"^[0-9+\-() ]{5,32}$")
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    preferred_language: str | None = Field(default=None, max_length=32)
    emergency_contact_name: str | None = Field(default=None, max_length=128)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    emergency_contact_relation: str | None = Field(default=None, max_length=32)
    allergies: list[Allergy] | None = None
    status: Literal["active", "inactive"] | None = None
    primary_department_id: int | None = None


class PatientListItem(ORMModel):
    id: int
    mrn: str
    full_name: str
    date_of_birth: date
    age: int
    sex: str
    status: str
    primary_department: str | None
    phone: str | None
    is_synthetic: bool


class PatientDemographics(PatientListItem):
    first_name: str
    last_name: str
    email: str | None
    address: str | None
    preferred_language: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_relation: str | None
    created_at: datetime


class DiagnosisOut(ORMModel):
    id: int
    icd10_code: str
    description: str
    category: str
    is_chronic: bool
    is_primary: bool
    status: str
    diagnosed_on: date
    admission_id: int | None


class CareTeamMember(BaseModel):
    user_id: int
    name: str
    care_role: str


class PatientClinical(PatientDemographics):
    blood_type: str | None
    allergies: list[Allergy]
    active_diagnoses: list[DiagnosisOut]
    current_medications: list[dict]
    current_admission: dict | None
    admission_count: int
    care_team: list[CareTeamMember]
