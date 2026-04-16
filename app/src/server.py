import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import initialize_database
from grotesk.infrastructure.db.session import build_engine, build_session_factory
from grotesk.presentation.api.main import create_app

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_config = DBConfig.from_env()
    engine = build_engine(db_config)
    session_factory = build_session_factory(engine)
    await initialize_database(engine, session_factory)

    app.state.session_factory = session_factory  # type: ignore

    yield

    await engine.dispose()


def main() -> None:
    app = create_app(lifespan=lifespan)

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    logging.info(f"Starting API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
