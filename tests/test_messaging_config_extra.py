from __future__ import annotations

from grotesk.infrastructure.messaging.config import MessagingConfig


def test_amqp_url_from_rabbit_env_defaults(monkeypatch) -> None:
    monkeypatch.delenv("RABBITMQ_DEFAULT_USER", raising=False)
    monkeypatch.delenv("RABBITMQ_DEFAULT_PASS", raising=False)
    monkeypatch.delenv("RABBITMQ_HOST", raising=False)
    monkeypatch.delenv("RABBITMQ_PORT", raising=False)
    assert MessagingConfig._amqp_url_from_rabbit_env() == "amqp://guest:guest@localhost:5672/"


def test_amqp_url_from_rabbit_env_quotes_credentials(monkeypatch) -> None:
    monkeypatch.setenv("RABBITMQ_DEFAULT_USER", "user name")
    monkeypatch.setenv("RABBITMQ_DEFAULT_PASS", "p@ss word")
    monkeypatch.setenv("RABBITMQ_HOST", "rabbit")
    monkeypatch.setenv("RABBITMQ_PORT", "5673")
    assert MessagingConfig._amqp_url_from_rabbit_env() == "amqp://user%20name:p%40ss%20word@rabbit:5673/"


def test_messaging_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGING_BACKEND", "rabbitmq")
    monkeypatch.setenv("RABBITMQ_DEFAULT_USER", "u")
    monkeypatch.setenv("RABBITMQ_DEFAULT_PASS", "")
    monkeypatch.setenv("RABBITMQ_HOST", "h")
    monkeypatch.setenv("RABBITMQ_PORT", "5678")
    monkeypatch.setenv("RABBITMQ_QUEUE_NAME", "queue")
    monkeypatch.setenv("RABBITMQ_PREFETCH_COUNT", "5")
    monkeypatch.setenv("RABBITMQ_DURABLE_QUEUE", "false")
    monkeypatch.setenv("WORKER_ID", "wid")
    monkeypatch.setenv("WORKER_PROCESSING_DELAY_SECONDS", "0.2")
    cfg = MessagingConfig.from_env()
    assert cfg.backend == "rabbitmq"
    assert cfg.amqp_url == "amqp://u:@h:5678/"
    assert cfg.queue_name == "queue"
    assert cfg.prefetch_count == 5
    assert cfg.durable_queue is False
    assert cfg.worker_id == "wid"
    assert cfg.processing_delay_seconds == 0.2
