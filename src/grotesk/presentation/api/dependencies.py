from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.identity_access.queries import GetUserById
from grotesk.domain.identity_access.model import UserId
from grotesk.main.application import Application
from grotesk.main.bootstrap import build_application

SESSION_USER_ID_KEY = "user_id"


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory  # type: ignore
    async with session_factory() as session:
        yield session


async def get_application(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Application:
    return build_application(session)


def login_user(request: Request, user_id: UserId) -> None:
    request.session[SESSION_USER_ID_KEY] = str(user_id.value)


def logout_user(request: Request) -> None:
    request.session.clear()


async def get_optional_current_user(
    request: Request,
    application: Annotated[Application, Depends(get_application)],
) -> UserDTO | None:
    raw_user_id = request.session.get(SESSION_USER_ID_KEY)
    if raw_user_id is None:
        return None

    try:
        return await application.get_user_by_id(GetUserById(user_id=UserId(UUID(str(raw_user_id)))))
    except (ValueError, TypeError):
        request.session.clear()
        return None


async def get_current_user(
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
) -> UserDTO:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return current_user


def resolve_user_id(user_id: UUID | None, current_user: UserDTO | None) -> UserId:
    if user_id is not None:
        return UserId(user_id)
    if current_user is not None:
        return current_user.user_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
