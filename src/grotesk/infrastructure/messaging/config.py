import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingConfig:
    backend: str
    amqp_url: str
    queue_name: str
    prefetch_count: int
    durable_queue: bool
    worker_id: str
    processing_delay_seconds: float

    @classmethod
    def from_env(cls) -> "MessagingConfig":
        backend = os.getenv("MESSAGING_BACKEND", "inmemory")
        host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        port = int(os.getenv("RABBITMQ_PORT", "5672"))
        user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        amqp_url = os.getenv("RABBITMQ_URL", f"amqp://{user}:{password}@{host}:{port}/")

        return cls(
            backend=backend,
            amqp_url=amqp_url,
            queue_name=os.getenv("RABBITMQ_QUEUE_NAME", "ml_tasks"),
            prefetch_count=int(os.getenv("RABBITMQ_PREFETCH_COUNT", "1")),
            durable_queue=os.getenv("RABBITMQ_DURABLE_QUEUE", "true").lower() == "true",
            worker_id=os.getenv("WORKER_ID", os.getenv("HOSTNAME", "worker")),
            processing_delay_seconds=float(os.getenv("WORKER_PROCESSING_DELAY_SECONDS", "0.5")),
        )
