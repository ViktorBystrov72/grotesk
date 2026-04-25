from uuid import UUID

from pydantic import BaseModel

from grotesk.domain.identity_access.model import UserRole


class RegisterRequest(BaseModel):
    email: str
    password: str


class RegisterResponse(BaseModel):
    user_id: UUID


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user_id: UUID


class LogoutResponse(BaseModel):
    status: str


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    role: UserRole
    is_active: bool
