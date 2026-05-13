import asyncio
from pathlib import Path

from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect

from alembic import command
from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.session import build_engine

BASELINE_REVISION = "0001_initial_schema"
REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = REPO_ROOT / "alembic"
APPLICATION_TABLES = {
    "account_balances",
    "attachment_assets",
    "billing_transactions",
    "credit_reservations",
    "job_history_records",
    "media_assets",
    "model_capabilities",
    "model_profiles",
    "pricing_rules",
    "processing_jobs",
    "top_up_requests",
    "users",
}


def build_alembic_config(db_url: str) -> AlembicConfig:
    config = AlembicConfig(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


async def _get_table_names(db_config: DBConfig) -> set[str]:
    engine = build_engine(db_config)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
    finally:
        await engine.dispose()


async def _stamp_existing_schema_if_needed(db_config: DBConfig) -> None:
    table_names = await _get_table_names(db_config)
    if "alembic_version" in table_names:
        return
    if not (APPLICATION_TABLES & table_names):
        return
    await asyncio.to_thread(command.stamp, build_alembic_config(db_config.url), BASELINE_REVISION)


async def run_migrations(db_config: DBConfig | None = None) -> None:
    resolved_db_config = db_config or DBConfig.from_env()
    await _stamp_existing_schema_if_needed(resolved_db_config)
    await asyncio.to_thread(command.upgrade, build_alembic_config(resolved_db_config.url), "head")
