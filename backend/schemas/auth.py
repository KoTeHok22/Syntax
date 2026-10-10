from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from backend.core.labels import Specialization


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["candidate", "employer"]
    consent_accepted: bool
    pvn_id: str | None = Field(default=None, max_length=64)
    specialization: Specialization | None = None
    grade: Literal["junior", "middle", "senior"] | None = None


class RegisterResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_email_confirmed: bool
    confirmation_url: str | None = None
    category_id: int | None = None


class EmailConfirmResponse(BaseModel):
    email: EmailStr
    is_email_confirmed: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    pvn_id: str | None
    is_email_confirmed: bool

    class Config:
        from_attributes = True
