import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import create_schema
from grotesk.infrastructure.db.session import build_engine, build_session_factory
from tests.support import DBContext


@pytest_asyncio.fixture()
async def db_context() -> AsyncIterator[DBContext]:
    db_file = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    db_file.close()
    db_path = Path(db_file.name)
    engine = build_engine(
        DBConfig(
            driver="sqlite+aiosqlite",
            host="",
            port=0,
            database=db_file.name,
            user="",
            password="",
            echo=False,
        ),
    )
    session_factory = build_session_factory(engine)
    await create_schema(engine)

    try:
        yield DBContext(engine=engine, session_factory=session_factory)
    finally:
        await engine.dispose()
        os.unlink(db_path)
