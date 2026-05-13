import asyncio

from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import initialize_database
from grotesk.infrastructure.db.session import build_engine, build_session_factory


async def run_migrate() -> None:
    db_config = DBConfig.from_env()
    engine = build_engine(db_config)
    session_factory = build_session_factory(engine)

    try:
        await initialize_database(engine, session_factory)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run_migrate())


if __name__ == "__main__":
    main()
