import os
from collections.abc import AsyncGenerator
from typing import Callable, Literal

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp

from grotesk.presentation.api.exceptions import setup_exception_handlers
from grotesk.presentation.api.routers import setup_routers
from grotesk.presentation.web import setup_web


def _session_middleware_factory(
    app: ASGIApp,
    *,
    secret_key: str,
    same_site: Literal["lax", "strict", "none"] = "lax",
    https_only: bool = False,
) -> ASGIApp:
    return SessionMiddleware(
        app,
        secret_key=secret_key,
        same_site=same_site,
        https_only=https_only,
    )


def create_app(lifespan: Callable[[FastAPI], AsyncGenerator] | None = None) -> FastAPI:
    app = FastAPI(
        title="Grotesk API",
        version="0.6.0",
        description="REST API for Grotesk ML Media Service",
        lifespan=lifespan,
    )

    app.add_middleware(
        _session_middleware_factory,
        secret_key=os.getenv("WEB_SESSION_SECRET", "grotesk-dev-session-secret"),
        same_site="lax",
        https_only=False,
    )
    setup_routers(app)
    setup_web(app)
    setup_exception_handlers(app)

    return app
