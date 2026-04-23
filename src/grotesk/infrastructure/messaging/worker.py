import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, cast
from uuid import uuid4

from aio_pika import connect_robust
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from grotesk.domain.billing.service import BillingService
from grotesk.domain.common.primitives import EntityId
from grotesk.domain.processing.model import JobResultRef, ProcessingStatus
from grotesk.domain.processing.service import ProcessingService
from grotesk.infrastructure.db.repositories.billing import (
    AccountBalanceRepositoryImpl,
    BillingTransactionRepositoryImpl,
    TopUpRequestRepositoryImpl,
)
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.session import session_scope
from grotesk.infrastructure.db.uow import SQLAlchemyUnitOfWork
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage
from grotesk.infrastructure.ml.artifacts import ResultArtifactStore
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.processor import HuggingFaceJobProcessor, JobProcessor

logger = logging.getLogger(__name__)


class JobNotReadyError(Exception):
    pass


class ProcessingWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        messaging_config: MessagingConfig,
        processor: JobProcessor | None = None,
        artifact_store: ResultArtifactStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._messaging_config = messaging_config
        self._ml_config = MLConfig.from_env()
        self._processor = processor or HuggingFaceJobProcessor(self._ml_config)
        self._artifact_store = artifact_store or ResultArtifactStore(self._ml_config.artifact_root)

    async def run(self) -> None:
        connection = await connect_robust(self._messaging_config.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=self._messaging_config.prefetch_count)
            queue = await channel.declare_queue(
                self._messaging_config.queue_name,
                durable=self._messaging_config.durable_queue,
            )

            consumer_callback = cast(Callable[[AbstractIncomingMessage], Awaitable[Any]], self._consume_message)
            await queue.consume(consumer_callback)

            logger.info(
                "Worker %s is consuming queue %s",
                self._messaging_config.worker_id,
                self._messaging_config.queue_name,
            )

            await asyncio.Future()

    async def process_message(self, payload: JobSubmittedMessage) -> None:
        async with session_scope(self._session_factory) as session:
            account_balance_repository = AccountBalanceRepositoryImpl(session)
            billing_transaction_repository = BillingTransactionRepositoryImpl(session)
            media_asset_repository = MediaAssetRepositoryImpl(session)
            model_catalog_repository = ModelCatalogRepositoryImpl(session)
            processing_job_repository = ProcessingJobRepositoryImpl(session)
            top_up_request_repository = TopUpRequestRepositoryImpl(session)
            billing_service = BillingService(
                account_balance_repository,
                top_up_request_repository,
                billing_transaction_repository,
            )
            processing_service = ProcessingService(processing_job_repository)
            uow = SQLAlchemyUnitOfWork(session)

            job = await processing_job_repository.get_by_id(payload.job_identifier)
            if job is None:
                raise JobNotReadyError(f"Job {payload.job_id} is not committed yet.")

            if job.status == ProcessingStatus.COMPLETED:
                logger.info("Job %s is already completed, skipping duplicate delivery.", payload.job_id)
                return

            if job.status == ProcessingStatus.FAILED:
                logger.info("Job %s is already failed, skipping duplicate delivery.", payload.job_id)
                return

            if job.status != ProcessingStatus.RUNNING:
                job.mark_running()
                await processing_job_repository.save(job)
                await uow.commit()

            try:
                media_asset = await media_asset_repository.get_by_id(job.media_asset_id)
                if media_asset is None:
                    raise ValueError(f"Media asset {job.media_asset_id.value} does not exist.")

                model_profile = await model_catalog_repository.get_by_id(job.model_id)
                if model_profile is None:
                    raise ValueError(f"Model profile {job.model_id.value} does not exist.")

                await asyncio.sleep(self._messaging_config.processing_delay_seconds)
                execution_result = await self._processor.process(job, media_asset, model_profile)
                result_identifier = uuid4()
                artifact_path = self._artifact_store.save(result_identifier, execution_result)
                completion_message = self._build_completion_message(
                    payload=payload,
                    job_type=str(job.job_type),
                    artifact_path=artifact_path,
                    payload_data=execution_result.history_payload,
                )
                await processing_service.complete_job(
                    payload.job_identifier,
                    JobResultRef(
                        result_type=execution_result.result_type,
                        result_id=EntityId(result_identifier),
                    ),
                    completion_message=completion_message,
                )
                await billing_service.confirm_reservation(job.user_id, job.id)
                await uow.commit()
            except Exception as error:
                await processing_service.fail_job(
                    payload.job_identifier,
                    f"Worker {self._messaging_config.worker_id} failed: {error}",
                )
                await billing_service.release_reservation(job.user_id, job.id)
                await uow.commit()
                raise

    async def _consume_message(self, message: AbstractIncomingMessage) -> None:
        try:
            payload = JobSubmittedMessage.from_body(message.body)
            await self.process_message(payload)
        except JobNotReadyError as error:
            logger.warning("%s Requeueing message.", error)
            await message.nack(requeue=True)
            return
        except Exception:
            logger.exception("Worker %s could not process message.", self._messaging_config.worker_id)
            await message.ack()
            return

        await message.ack()

    def _build_completion_message(
        self,
        payload: JobSubmittedMessage,
        job_type: str,
        artifact_path: Path,
        payload_data: dict[str, object],
    ) -> str:
        return json.dumps(
            {
                "job_id": str(payload.job_id),
                "job_type": job_type,
                "worker_id": self._messaging_config.worker_id,
                "artifact_path": str(artifact_path),
                "result": payload_data,
                "processed_at": datetime.now(UTC).isoformat(),
            },
            sort_keys=True,
        )
