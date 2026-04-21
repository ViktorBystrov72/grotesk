import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from aio_pika import IncomingMessage, connect_robust
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from grotesk.domain.common.primitives import EntityId
from grotesk.domain.processing.model import JobResultRef, ProcessingStatus
from grotesk.domain.processing.service import ProcessingService
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.session import session_scope
from grotesk.infrastructure.db.uow import SQLAlchemyUnitOfWork
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage

logger = logging.getLogger(__name__)


class JobNotReadyError(Exception):
    pass


class ProcessingWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        messaging_config: MessagingConfig,
    ) -> None:
        self._session_factory = session_factory
        self._messaging_config = messaging_config

    async def run(self) -> None:
        connection = await connect_robust(self._messaging_config.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=self._messaging_config.prefetch_count)
            queue = await channel.declare_queue(
                self._messaging_config.queue_name,
                durable=self._messaging_config.durable_queue,
            )

            await queue.consume(self._consume_message)

            logger.info(
                "Worker %s is consuming queue %s",
                self._messaging_config.worker_id,
                self._messaging_config.queue_name,
            )

            await asyncio.Future()

    async def process_message(self, payload: JobSubmittedMessage) -> None:
        async with session_scope(self._session_factory) as session:
            processing_job_repository = ProcessingJobRepositoryImpl(session)
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
                await asyncio.sleep(self._messaging_config.processing_delay_seconds)
                completion_message = self._build_completion_message(payload, job.job_type.value)
                await processing_service.complete_job(
                    payload.job_identifier,
                    JobResultRef(
                        result_type="job_history",
                        result_id=EntityId(uuid4()),
                    ),
                    completion_message=completion_message,
                )
                await uow.commit()
            except Exception as error:
                await processing_service.fail_job(
                    payload.job_identifier,
                    f"Worker {self._messaging_config.worker_id} failed: {error}",
                )
                await uow.commit()
                raise

    async def _consume_message(self, message: IncomingMessage) -> None:
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

    def _build_completion_message(self, payload: JobSubmittedMessage, job_type: str) -> str:
        prediction = self._build_prediction(job_type)
        return json.dumps(
            {
                "job_id": str(payload.job_id),
                "job_type": job_type,
                "worker_id": self._messaging_config.worker_id,
                "prediction": prediction,
                "processed_at": datetime.now(UTC).isoformat(),
            },
            sort_keys=True,
        )

    def _build_prediction(self, job_type: str) -> dict[str, object]:
        if job_type == "transcription":
            return {
                "confidence": 0.98,
                "text": "Mock transcription completed successfully.",
            }

        return {
            "operations_applied": 1,
            "summary": "Mock video edit completed successfully.",
        }
