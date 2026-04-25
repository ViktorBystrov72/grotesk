import logging

from aio_pika import DeliveryMode, Message, connect_robust

from grotesk.domain.common.event import Event
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage

logger = logging.getLogger(__name__)


class RabbitMQEventPublisher:
    def __init__(self, config: MessagingConfig) -> None:
        self._config = config

    async def publish(self, events: list[Event]) -> None:
        messages = [message for event in events if (message := JobSubmittedMessage.from_event(event)) is not None]
        if not messages:
            return

        connection = await connect_robust(self._config.amqp_url)
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(
                self._config.queue_name,
                durable=self._config.durable_queue,
            )

            for payload in messages:
                await channel.default_exchange.publish(
                    Message(
                        body=payload.to_body(),
                        content_type="application/json",
                        delivery_mode=DeliveryMode.PERSISTENT,
                    ),
                    routing_key=queue.name,
                )

                logger.info(
                    "Published job %s to queue %s",
                    payload.job_id,
                    self._config.queue_name,
                )
