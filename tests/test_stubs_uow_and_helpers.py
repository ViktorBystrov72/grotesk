from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.exc import SQLAlchemyError

from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    TopUpRequest,
    TopUpRequestId,
    TransactionType,
)
from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile
from grotesk.domain.common.primitives import FileLocation, Money
from grotesk.domain.identity_access.model import Credential, Email, PasswordHash, User, UserId, UserRole
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.domain.processing.model import JobId, JobType, ProcessingJob
from grotesk.infrastructure.db.uow import SQLAlchemyUnitOfWork
from grotesk.infrastructure.stubs import (
    InMemoryAccountBalanceRepository,
    InMemoryBillingTransactionRepository,
    InMemoryEventPublisher,
    InMemoryMediaAssetRepository,
    InMemoryModelCatalogRepository,
    InMemoryProcessingJobRepository,
    InMemoryTopUpRequestRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)
from grotesk.presentation import helpers


def _user() -> User:
    return User(
        id=UserId(UUID("00000000-0000-0000-0000-000000000001")),
        credential=Credential(email=Email("u@example.com"), password_hash=PasswordHash("hash")),
        role=UserRole.CUSTOMER,
    )


def _media() -> MediaAsset:
    return MediaAsset(
        id=MediaAssetId(UUID("00000000-0000-0000-0000-000000000002")),
        owner_id=UserId(UUID("00000000-0000-0000-0000-000000000001")),
        media_type=MediaType.AUDIO,
        location=FileLocation("/tmp/a.wav"),
    )


@pytest.mark.asyncio
async def test_inmemory_stubs_cover_all_methods() -> None:
    uow = InMemoryUnitOfWork()
    await uow.commit()
    await uow.rollback()

    publisher = InMemoryEventPublisher()
    await publisher.publish([SimpleNamespace(), SimpleNamespace()])  # type: ignore[list-item]
    assert len(publisher.published_events) == 2

    user_repo = InMemoryUserRepository()
    user = _user()
    await user_repo.add(user)
    assert await user_repo.get_by_id(user.id) == user
    assert await user_repo.get_by_email(user.credential.email) == user

    balance_repo = InMemoryAccountBalanceRepository()
    balance = AccountBalance(user_id=user.id, available=Money(Decimal("10")))
    await balance_repo.save(balance)
    assert await balance_repo.get_by_user_id(user.id) == balance

    top_up_repo = InMemoryTopUpRequestRepository()
    req = TopUpRequest(id=TopUpRequestId(UUID(int=10)), user_id=user.id, amount=Money(Decimal("5")))
    await top_up_repo.add(req)
    assert await top_up_repo.get_by_id(req.id) == req
    await top_up_repo.save(req)

    tx_repo = InMemoryBillingTransactionRepository()
    tx = BillingTransaction(
        id=SimpleNamespace(value=UUID(int=11)),
        user_id=user.id,
        amount=Money(Decimal("1")),
        transaction_type=TransactionType.TOP_UP,
        created_at=datetime.now(UTC),
    )
    await tx_repo.add(tx)
    assert await tx_repo.get_by_id(SimpleNamespace(value=UUID(int=11))) == tx
    assert (await tx_repo.list_by_user_id(user.id))[0] == tx

    media_repo = InMemoryMediaAssetRepository()
    media = _media()
    await media_repo.add(media)
    assert await media_repo.get_by_id(media.id) == media
    await media_repo.save(media)

    model_repo = InMemoryModelCatalogRepository()
    model = ModelProfile(id=ModelId(UUID(int=12)), name="m", capabilities=[Capability.TRANSCRIPTION], pricing_rules=[])
    await model_repo.save(model)
    assert await model_repo.get_by_id(model.id) == model

    job_repo = InMemoryProcessingJobRepository()
    job = ProcessingJob(
        id=JobId(UUID(int=13)),
        user_id=user.id,
        media_asset_id=media.id,
        model_id=model.id,
        job_type=JobType.TRANSCRIPTION,
        estimated_cost=Money(Decimal("1")),
    )
    await job_repo.add(job)
    assert await job_repo.get_by_id(job.id) == job
    await job_repo.save(job)


@pytest.mark.asyncio
async def test_sqlalchemy_uow_commit_and_rollback() -> None:
    class _Session:
        def __init__(self):
            self.committed = False
            self.rolled_back = False

        async def commit(self):
            self.committed = True

        async def rollback(self):
            self.rolled_back = True

    session = _Session()
    uow = SQLAlchemyUnitOfWork(session)  # type: ignore[arg-type]
    await uow.commit()
    assert session.committed is True
    await uow.rollback()
    assert session.rolled_back is True

    class _FailingSession(_Session):
        async def commit(self):
            raise SQLAlchemyError("boom")

    failing = _FailingSession()
    uow = SQLAlchemyUnitOfWork(failing)  # type: ignore[arg-type]
    with pytest.raises(SQLAlchemyError):
        await uow.commit()
    assert failing.rolled_back is True


@pytest.mark.asyncio
async def test_presentation_helpers_branches(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(tmp_path))
    assert helpers.get_media_storage_root() == tmp_path
    assert helpers.detect_media_type("a.wav") == MediaType.AUDIO
    assert helpers.detect_media_type("a.bin", "video/mp4") == MediaType.VIDEO
    assert helpers.detect_media_type("a.bin", "image/png") == MediaType.IMAGE
    with pytest.raises(ValueError):
        helpers.detect_media_type("a.bin", "application/octet-stream")

    upload = SimpleNamespace(
        filename="voice.wav",
        content_type="audio/wav",
        read=lambda: None,
        close=lambda: None,
    )

    async def _read():
        return b"bytes"

    async def _close():
        return None

    upload.read = _read
    upload.close = _close
    saved = await helpers.save_upload_file(upload, MediaType.AUDIO)  # type: ignore[arg-type]
    assert saved.exists()

    no_name_upload = SimpleNamespace(filename=None, content_type="audio/wav", read=_read, close=_close)
    saved2 = await helpers.save_upload_file(no_name_upload, MediaType.AUDIO)  # type: ignore[arg-type]
    assert saved2.suffix == ".bin"

    monkeypatch.setattr(
        "grotesk.presentation.helpers.MLConfig.from_env", lambda: SimpleNamespace(artifact_root=str(tmp_path))
    )
    result_id = UUID(int=20)
    art_dir = tmp_path / "transcription"
    art_dir.mkdir(parents=True, exist_ok=True)
    artifact = art_dir / f"{result_id}.json"
    artifact.write_text("{}", encoding="utf-8")
    assert helpers.resolve_result_artifact_path("transcription", result_id) == artifact
    assert helpers.resolve_result_artifact_path(None, result_id) is None
    assert helpers.resolve_result_artifact_path("transcription", None) is None

    assert helpers.load_json_artifact(None) is None
    assert helpers.load_json_artifact(tmp_path / "x.txt") is None
    assert helpers.load_json_artifact(artifact) == {}

    assert helpers.probe_media_duration_seconds(None) is None
    assert helpers.probe_media_duration_seconds("/missing/file") is None

    media = tmp_path / "a.wav"
    media.write_bytes(b"wav")

    monkeypatch.setattr(
        "grotesk.presentation.helpers.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="12.5"),
    )
    monkeypatch.setattr(
        "grotesk.presentation.helpers.MLConfig.from_env", lambda: SimpleNamespace(ffprobe_binary="ffprobe")
    )
    assert helpers.probe_media_duration_seconds(str(media)) == 12.5

    monkeypatch.setattr(
        "grotesk.presentation.helpers.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad")),
    )
    assert helpers.probe_media_duration_seconds(str(media)) is None

    async def _upload_media(command):
        return command.asset

    application = SimpleNamespace(upload_media=_upload_media)
    uploaded = await helpers.register_uploaded_media(application, _user().id, upload)  # type: ignore[arg-type]
    assert uploaded.owner_id == _user().id
    assert uploaded.media_type == MediaType.AUDIO
    assert json.loads(json.dumps({"k": "v"})) == {"k": "v"}
