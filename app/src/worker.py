import asyncio
import logging

from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import wait_for_database
from grotesk.infrastructure.db.session import build_engine, build_session_factory
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.worker import ProcessingWorker

logging.basicConfig(level=logging.INFO)


async def run_worker() -> None:
    db_config = DBConfig.from_env()
    messaging_config = MessagingConfig.from_env()

    engine = build_engine(db_config)
    session_factory = build_session_factory(engine)

    await wait_for_database(engine)

    worker = ProcessingWorker(session_factory, messaging_config)
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
