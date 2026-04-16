from collections.abc import AsyncGenerator
from typing import Callable

from fastapi import FastAPI

from grotesk.presentation.api.routers import setup_routers
from grotesk.presentation.api.exceptions import setup_exception_handlers


def create_app(lifespan: Callable[[FastAPI], AsyncGenerator] | None = None) -> FastAPI:
    app = FastAPI(
        title="Grotesk API",
        version="0.4.0",
        description="REST API for Grotesk ML Media Service",
        lifespan=lifespan,
    )

    setup_routers(app)
    setup_exception_handlers(app)

    return app
