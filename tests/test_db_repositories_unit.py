from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from grotesk.domain.identity_access.model import Email, User, UserId, UserRole
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository
from grotesk.infrastructure.db.repositories.billing import (
    AccountBalanceRepositoryImpl,
    BillingTransactionRepositoryImpl,
    TopUpRequestRepositoryImpl,
)
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.repositories.user import UserRepositoryImpl


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)

    def __iter__(self):
        return iter(self._items)


class _Session:
    def __init__(self):
        self.added = []
        self.scalar_result = None
        self.get_result = None
        self.scalars_result = _ScalarsResult([])

    async def scalar(self, _query):
        return self.scalar_result

    async def get(self, _model, _key):
        return self.get_result

    async def scalars(self, _query):
        return self.scalars_result

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None


def test_base_repository_stores_session():
    session = _Session()
    repo = SQLAlchemyRepository(session)  # type: ignore[arg-type]
    assert repo._session is session  # noqa: SLF001


@pytest.mark.asyncio
async def test_user_repository_branches(monkeypatch):
    session = _Session()
    repo = UserRepositoryImpl(session)  # type: ignore[arg-type]
    monkeypatch.setattr("grotesk.infrastructure.db.repositories.user.user_to_domain", lambda model: ("user", model))
    user = User(
        id=UserId(UUID("00000000-0000-0000-0000-000000000001")),
        credential=SimpleNamespace(email=Email("a@b"), password_hash=SimpleNamespace(value="h")),
        role=UserRole.CUSTOMER,
    )
    await repo.add(user)
    session.get_result = SimpleNamespace()
    assert (await repo.get_by_id(user.id))[0] == "user"
    session.get_result = None
    assert await repo.get_by_id(user.id) is None
    session.scalar_result = SimpleNamespace()
    assert (await repo.get_by_email(Email("a@b")))[0] == "user"
    session.scalar_result = None
    assert await repo.get_by_email(Email("a@b")) is None


@pytest.mark.asyncio
async def test_catalog_repository_branches(monkeypatch):
    session = _Session()
    repo = ModelCatalogRepositoryImpl(session)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.catalog.model_profile_to_domain", lambda model: ("m", model)
    )
    session.scalar_result = None
    assert await repo.get_by_id(SimpleNamespace(value=UUID(int=1))) is None
    session.scalar_result = SimpleNamespace()
    assert (await repo.get_by_id(SimpleNamespace(value=UUID(int=1))))[0] == "m"
    session.scalars_result = _ScalarsResult([SimpleNamespace(), SimpleNamespace()])
    assert len(await repo.list_active()) == 2


@pytest.mark.asyncio
async def test_media_repository_branches(monkeypatch):
    session = _Session()
    repo = MediaAssetRepositoryImpl(session)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.media.media_asset_to_domain", lambda model: ("a", model)
    )
    asset = SimpleNamespace(
        id=SimpleNamespace(value=UUID(int=1)),
        owner_id=SimpleNamespace(value=UUID(int=2)),
        media_type="audio",
        location=SimpleNamespace(storage_key="x"),
        status="uploaded",
        attachments=[],
    )
    await repo.add(asset)
    session.scalar_result = None
    assert await repo.get_by_id(SimpleNamespace(value=UUID(int=1))) is None
    session.scalar_result = SimpleNamespace()
    assert (await repo.get_by_id(SimpleNamespace(value=UUID(int=1))))[0] == "a"
    session.scalar_result = None
    await repo.save(asset)  # falls back to add
    session.scalar_result = SimpleNamespace(attachments=[])
    await repo.save(asset)  # update branch


@pytest.mark.asyncio
async def test_processing_repository_branches(monkeypatch):
    session = _Session()
    repo = ProcessingJobRepositoryImpl(session)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.processing.processing_job_to_domain", lambda model: ("j", model)
    )
    job = SimpleNamespace(
        id=SimpleNamespace(value=UUID(int=1)),
        user_id=SimpleNamespace(value=UUID(int=2)),
        media_asset_id=SimpleNamespace(value=UUID(int=3)),
        model_id=SimpleNamespace(value=UUID(int=4)),
        job_type="transcription",
        estimated_cost=SimpleNamespace(amount=1, currency="CREDIT"),
        prompt_text="p",
        operations=[],
        status="queued",
        result_ref=None,
        history=[],
    )
    await repo.add(job)
    session.scalar_result = None
    assert await repo.get_by_id(SimpleNamespace(value=UUID(int=1))) is None
    session.scalar_result = SimpleNamespace()
    assert (await repo.get_by_id(SimpleNamespace(value=UUID(int=1))))[0] == "j"
    session.scalars_result = _ScalarsResult([SimpleNamespace()])
    assert len(await repo.list_by_user_id(SimpleNamespace(value=UUID(int=2)))) == 1
    session.scalar_result = None
    await repo.save(job)  # add branch
    session.scalar_result = SimpleNamespace(history=[])
    await repo.save(job)  # update branch


@pytest.mark.asyncio
async def test_billing_repositories_branches(monkeypatch):
    session = _Session()
    account_repo = AccountBalanceRepositoryImpl(session)  # type: ignore[arg-type]
    topup_repo = TopUpRequestRepositoryImpl(session)  # type: ignore[arg-type]
    tx_repo = BillingTransactionRepositoryImpl(session)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.billing.account_balance_to_domain", lambda model: ("ab", model)
    )
    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.billing.top_up_request_to_domain", lambda model: ("tu", model)
    )
    monkeypatch.setattr(
        "grotesk.infrastructure.db.repositories.billing.billing_transaction_to_domain", lambda model: ("tx", model)
    )

    user_id = SimpleNamespace(value=UUID(int=1))
    session.scalar_result = None
    assert await account_repo.get_by_user_id(user_id) is None
    session.scalar_result = SimpleNamespace(reservations=[])
    assert (await account_repo.get_by_user_id(user_id))[0] == "ab"

    account = SimpleNamespace(
        user_id=user_id,
        available=SimpleNamespace(amount=1, currency="CREDIT"),
        reservations=[],
    )
    session.scalar_result = None
    await account_repo.save(account)
    session.scalar_result = SimpleNamespace(reservations=[])
    await account_repo.save(account)

    req = SimpleNamespace(
        id=SimpleNamespace(value=UUID(int=2)),
        user_id=user_id,
        amount=SimpleNamespace(amount=1, currency="CREDIT"),
        status="pending",
    )
    await topup_repo.add(req)
    session.get_result = None
    assert await topup_repo.get_by_id(SimpleNamespace(value=UUID(int=2))) is None
    session.get_result = SimpleNamespace()
    assert (await topup_repo.get_by_id(SimpleNamespace(value=UUID(int=2))))[0] == "tu"
    session.get_result = None
    await topup_repo.save(req)
    session.get_result = SimpleNamespace()
    await topup_repo.save(req)

    tx = SimpleNamespace(
        id=SimpleNamespace(value=UUID(int=3)),
        user_id=user_id,
        amount=SimpleNamespace(amount=1, currency="CREDIT"),
        transaction_type="top_up",
        related_job_id=None,
    )
    await tx_repo.add(tx)
    session.get_result = None
    assert await tx_repo.get_by_id(SimpleNamespace(value=UUID(int=3))) is None
    session.get_result = SimpleNamespace()
    assert (await tx_repo.get_by_id(SimpleNamespace(value=UUID(int=3))))[0] == "tx"
    session.scalars_result = _ScalarsResult([SimpleNamespace()])
    assert len(await tx_repo.list_by_user_id(user_id)) == 1
