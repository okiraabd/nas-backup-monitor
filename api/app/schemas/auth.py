"""Auth request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials submitted by a dashboard user or machine account."""

    username: str = Field(..., description="Account username.")
    password: str = Field(..., description="Plaintext password submitted only for login.")


class UserPublic(BaseModel):
    """User info returned to clients (never includes password hash)."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal user ID.")
    username: str = Field(..., description="Login username.")
    display_name: str = Field(..., description="Human-readable account name.")
    role: str = Field(..., description="Role used by RBAC: admin, operator, service, or collector.")
    is_active: bool = Field(..., description="Inactive users cannot authenticate.")
    last_login_at: datetime | None = Field(None, description="Last successful login time.")


class LoginResponse(BaseModel):
    """JWT response returned after login or refresh."""

    access_token: str = Field(..., description="JWT bearer token.")
    token_type: str = Field("bearer", description="Token type used in Authorization header.")
    user: UserPublic = Field(..., description="Authenticated user profile.")


class MessageResponse(BaseModel):
    """Simple message wrapper for command-style endpoints."""

    message: str = Field(..., description="Human-readable operation result.")
