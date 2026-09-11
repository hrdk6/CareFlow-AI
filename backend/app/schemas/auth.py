from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    permissions: list[str]
    doctor_id: int | None
    department_id: int | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
