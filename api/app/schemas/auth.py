"""Auth request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    """User info returned to clients (never includes password hash)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(BaseModel):
    message: str
