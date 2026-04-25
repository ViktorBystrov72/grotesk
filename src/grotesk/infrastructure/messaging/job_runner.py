import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from grotesk.domain.processing.model import JobId
from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.session import build_engine, build_session_factory, session_scope
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.processor import HuggingFaceJobProcessor
from grotesk.infrastructure.ml.types import JobExecutionResult


def serialize_execution_result(result: JobExecutionResult) -> dict[str, object]:
    return {
        "result_type": result.result_type,
        "artifact_extension": result.artifact_extension,
        "history_payload": result.history_payload,
        "artifact_payload": result.artifact_payload,
        "artifact_source": str(result.artifact_source) if result.artifact_source is not None else None,
    }


async def run_job(job_id: JobId, result_path: Path) -> None:
    engine = build_engine(DBConfig.from_env())
    session_factory = build_session_factory(engine)
    processor = HuggingFaceJobProcessor(MLConfig.from_env())

    try:
        async with session_scope(session_factory) as session:
            processing_job_repository = ProcessingJobRepositoryImpl(session)
            media_asset_repository = MediaAssetRepositoryImpl(session)
            model_catalog_repository = ModelCatalogRepositoryImpl(session)

            job = await processing_job_repository.get_by_id(job_id)
            if job is None:
                raise ValueError(f"Processing job {job_id.value} does not exist.")

            media_asset = await media_asset_repository.get_by_id(job.media_asset_id)
            if media_asset is None:
                raise ValueError(f"Media asset {job.media_asset_id.value} does not exist.")

            model_profile = await model_catalog_repository.get_by_id(job.model_id)
            if model_profile is None:
                raise ValueError(f"Model profile {job.model_id.value} does not exist.")

            result = await processor.process(job, media_asset, model_profile)

        result_path.write_text(
            json.dumps(serialize_execution_result(result), ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    finally:
        await engine.dispose()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m grotesk.infrastructure.messaging.job_runner <job_id> <result_path>")

    job_id = JobId(UUID(sys.argv[1]))
    result_path = Path(sys.argv[2])
    asyncio.run(run_job(job_id, result_path))


if __name__ == "__main__":
    main()
