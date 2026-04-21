from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from grotesk.main.application import Application
from grotesk.main.bootstrap import build_application


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory  # type: ignore
    async with session_factory() as session:
        yield session


async def get_application(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Application:
    return build_application(session)
