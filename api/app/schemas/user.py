"""User management request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import VALID_ROLES


class UserOut(BaseModel):
    """User representation returned by the management endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal user ID.")
    username: str = Field(..., description="Login username.")
    display_name: str = Field(..., description="Human-readable account name.")
    role: str = Field(..., description="RBAC role: admin, operator, service, or collector.")
    is_active: bool = Field(..., description="Inactive users cannot authenticate.")
    created_by: int | None = Field(None, description="Admin user ID that created this account.")
    last_login_at: datetime | None = Field(None, description="Last successful login time.")
    created_at: datetime = Field(..., description="Account creation time.")
    updated_at: datetime = Field(..., description="Last account update time.")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Unique login username.")
    password: str = Field(..., min_length=6, max_length=128, description="Initial plaintext password.")
    display_name: str = Field(..., min_length=1, max_length=128, description="Human-readable account name.")
    role: str = Field(..., description="RBAC role to assign.")

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class UserUpdate(BaseModel):
    """Partial update. Username is immutable; role/display_name/is_active editable."""
    display_name: str | None = Field(None, min_length=1, max_length=128, description="New display name.")
    role: str | None = Field(None, description="New RBAC role.")
    is_active: bool | None = Field(None, description="Whether the user may authenticate.")

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class PasswordUpdate(BaseModel):
    """Admin request to set a user's password."""

    new_password: str = Field(..., min_length=6, max_length=128, description="New plaintext password.")


class RotateTokenResponse(BaseModel):
    """Returned once after rotating a service/collector account's password."""
    user_id: int = Field(..., description="User ID whose password was rotated.")
    username: str = Field(..., description="Machine account username.")
    new_password: str = Field(..., description="New one-time plaintext password.")
    message: str = Field(
        "Store this password now; it will not be shown again.",
        description="Reminder that the plaintext password is returned once.",
    )
