from typing import Annotated
from uuid import uuid4

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request

from grotesk.application.identity_access.commands import RegisterUser
from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.identity_access.queries import GetUserByEmail
from grotesk.domain.identity_access.model import UserId
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import (
    get_application,
    get_current_user,
    login_user,
    logout_user,
)
from grotesk.presentation.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
)

router = APIRouter()

_BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_bytes(plain: str) -> bytes:
    data = plain.encode("utf-8")
    if len(data) > _BCRYPT_MAX_PASSWORD_BYTES:
        return data[:_BCRYPT_MAX_PASSWORD_BYTES]
    return data


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or not hashed_password.startswith("$2"):
        return False
    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    http_request: Request,
    application: Annotated[Application, Depends(get_application)],
) -> RegisterResponse:
    user_id = UserId(uuid4())
    command = RegisterUser(
        user_id=user_id,
        email=request.email,
        password_hash=get_password_hash(request.password),
    )
    try:
        await application.register_user(command)
        login_user(http_request, user_id)
        return RegisterResponse(user_id=user_id.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    application: Annotated[Application, Depends(get_application)],
) -> LoginResponse:
    query = GetUserByEmail(email=request.email)
    try:
        user_dto = await application.get_user_by_email(query)
        if not verify_password(request.password, user_dto.password_hash):
            raise ValueError("Invalid credentials")
        login_user(http_request, user_dto.user_id)
        return LoginResponse(user_id=user_dto.user_id.value)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout", response_model=LogoutResponse)
async def logout(http_request: Request) -> LogoutResponse:
    logout_user(http_request)
    return LogoutResponse(status="success")


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[UserDTO, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        user_id=current_user.user_id.value,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
    )
