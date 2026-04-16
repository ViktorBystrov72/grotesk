from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext

from grotesk.application.identity_access.commands import RegisterUser
from grotesk.application.identity_access.queries import GetUserByEmail
from grotesk.domain.identity_access.model import UserId
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
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
        return RegisterResponse(user_id=user_id.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    application: Annotated[Application, Depends(get_application)],
) -> LoginResponse:
    query = GetUserByEmail(email=request.email)
    try:
        user_dto = await application.get_user_by_email(query)
        if not verify_password(request.password, user_dto.password_hash):
            raise ValueError("Invalid credentials")
        return LoginResponse(user_id=user_dto.user_id.value)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
