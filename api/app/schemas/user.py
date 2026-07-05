"""User management request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import VALID_ROLES


class UserOut(BaseModel):
    """User representation returned by the management endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_by: int | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    role: str

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class UserUpdate(BaseModel):
    """Partial update. Username is immutable; role/display_name/is_active editable."""
    display_name: str | None = Field(None, min_length=1, max_length=128)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class PasswordUpdate(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class RotateTokenResponse(BaseModel):
    """Returned once after rotating a service/collector account's password."""
    user_id: int
    username: str
    new_password: str
    message: str = "Store this password now; it will not be shown again."
