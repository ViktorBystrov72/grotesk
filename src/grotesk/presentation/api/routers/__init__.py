from fastapi import FastAPI

from .auth import router as auth_router
from .balance import router as balance_router
from .health import router as health_router
from .history import router as history_router
from .predict import router as predict_router


def setup_routers(app: FastAPI) -> None:
    app.include_router(health_router, prefix="/health", tags=["System"])
    app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    app.include_router(balance_router, prefix="/balance", tags=["Balance"])
    app.include_router(predict_router, prefix="/predict", tags=["Predict"])
    app.include_router(history_router, prefix="/history", tags=["History"])
