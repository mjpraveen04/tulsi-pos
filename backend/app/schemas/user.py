from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole

PIN_PATTERN = r"^\d{4}$"


class UserPublic(BaseModel):
    """Safe projection — never carries the PIN hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: UserRole


class UserDetail(UserPublic):
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    user_id: int
    pin: str = Field(pattern=PIN_PATTERN, description="4-digit PIN")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: UserRole
    pin: str = Field(pattern=PIN_PATTERN)


class UserUpdate(BaseModel):
    """All fields optional: rename, change role, or reset the PIN (FR-10)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    pin: str | None = Field(default=None, pattern=PIN_PATTERN)
