import os
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class MessagingConfig:
    backend: str
    amqp_url: str
    queue_name: str
    prefetch_count: int
    durable_queue: bool
    worker_id: str
    processing_delay_seconds: float

    @staticmethod
    def _amqp_url_from_rabbit_env() -> str:
        user = os.environ.get("RABBITMQ_DEFAULT_USER", "guest")
        if "RABBITMQ_DEFAULT_PASS" in os.environ:
            password = os.environ["RABBITMQ_DEFAULT_PASS"]  # may be "" for no password
        else:
            password = "guest"
        host = os.environ.get("RABBITMQ_HOST", "localhost")
        port = int(os.environ.get("RABBITMQ_PORT", "5672"))
        u = quote(user, safe="")
        p = quote(password, safe="")
        return f"amqp://{u}:{p}@{host}:{port}/"

    @classmethod
    def from_env(cls) -> "MessagingConfig":
        backend = os.getenv("MESSAGING_BACKEND", "inmemory")
        amqp_url = cls._amqp_url_from_rabbit_env()
        return cls(
            backend=backend,
            amqp_url=amqp_url,
            queue_name=os.getenv("RABBITMQ_QUEUE_NAME", "ml_tasks"),
            prefetch_count=int(os.getenv("RABBITMQ_PREFETCH_COUNT", "1")),
            durable_queue=os.getenv("RABBITMQ_DURABLE_QUEUE", "true").lower() == "true",
            worker_id=os.getenv("WORKER_ID", os.getenv("HOSTNAME", "worker")),
            processing_delay_seconds=float(os.getenv("WORKER_PROCESSING_DELAY_SECONDS", "0.5")),
        )
