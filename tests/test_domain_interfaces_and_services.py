from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from grotesk.domain.billing.interfaces import (
    AccountBalanceRepository,
    BillingTransactionRepository,
    TopUpRequestRepository,
)
from grotesk.domain.billing.model import AccountBalance, Money, TopUpRequest, TopUpRequestId
from grotesk.domain.billing.service import BillingService
from grotesk.domain.catalog.interfaces import ModelCatalogRepository
from grotesk.domain.catalog.model import ModelId
from grotesk.domain.identity_access.interfaces import UserRepository
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.interfaces import MediaAssetRepository
from grotesk.domain.media_ingestion.model import MediaAssetId
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId
from grotesk.domain.processing.service import ProcessingService


@pytest.mark.asyncio
async def test_protocol_methods_raise_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await AccountBalanceRepository.get_by_user_id(object(), UserId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await AccountBalanceRepository.save(object(), object())
    with pytest.raises(NotImplementedError):
        await TopUpRequestRepository.add(object(), object())
    with pytest.raises(NotImplementedError):
        await TopUpRequestRepository.get_by_id(object(), TopUpRequestId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await TopUpRequestRepository.save(object(), object())
    with pytest.raises(NotImplementedError):
        await BillingTransactionRepository.add(object(), object())
    with pytest.raises(NotImplementedError):
        await BillingTransactionRepository.get_by_id(object(), object())
    with pytest.raises(NotImplementedError):
        await BillingTransactionRepository.list_by_user_id(object(), UserId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await UserRepository.add(object(), object())
    with pytest.raises(NotImplementedError):
        await UserRepository.get_by_id(object(), UserId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await UserRepository.get_by_email(object(), object())
    with pytest.raises(NotImplementedError):
        await ModelCatalogRepository.get_by_id(object(), ModelId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await ModelCatalogRepository.list_active(object())
    with pytest.raises(NotImplementedError):
        await ModelCatalogRepository.save(object(), object())
    with pytest.raises(NotImplementedError):
        await MediaAssetRepository.add(object(), object())
    with pytest.raises(NotImplementedError):
        await MediaAssetRepository.get_by_id(object(), MediaAssetId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await MediaAssetRepository.save(object(), object())
    with pytest.raises(NotImplementedError):
        await ProcessingJobRepository.add(object(), object())
    with pytest.raises(NotImplementedError):
        await ProcessingJobRepository.get_by_id(object(), JobId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await ProcessingJobRepository.list_by_user_id(object(), UserId(UUID(int=1)))
    with pytest.raises(NotImplementedError):
        await ProcessingJobRepository.save(object(), object())


@pytest.mark.asyncio
async def test_billing_and_processing_services_error_branches() -> None:
    user_id = UserId(UUID(int=1))
    job_id = JobId(UUID(int=2))
    amount = Money(Decimal("1"))

    async def _none(*_args, **_kwargs):
        return None

    account_repo = SimpleNamespace(get_by_user_id=_none, save=_none)
    topup_repo = SimpleNamespace(get_by_id=_none, save=_none)
    tx_repo = SimpleNamespace(add=_none)

    service = BillingService(account_repo, topup_repo, tx_repo)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await service.reserve_credits(user_id, job_id, amount)
    with pytest.raises(ValueError):
        await service.confirm_reservation(user_id, job_id)
    with pytest.raises(ValueError):
        await service.release_reservation(user_id, job_id)
    with pytest.raises(ValueError):
        await service.top_up_balance(user_id, amount)
    with pytest.raises(ValueError):
        await service.debit_balance(user_id, amount)
    with pytest.raises(ValueError):
        await service.approve_top_up(TopUpRequestId(UUID(int=3)))

    async def _get_by_user(_u):
        return AccountBalance(user_id=user_id, available=Money(Decimal("0")))

    async def _get_request(_i):
        return TopUpRequest(id=TopUpRequestId(UUID(int=4)), user_id=user_id, amount=Money(Decimal("2")))

    calls = {"saved_req": False}

    async def _save_req(_r):
        calls["saved_req"] = True

    service = BillingService(
        SimpleNamespace(get_by_user_id=_get_by_user, save=_none),
        SimpleNamespace(get_by_id=_get_request, save=_save_req),
        SimpleNamespace(add=_none),
    )  # type: ignore[arg-type]
    await service.approve_top_up(TopUpRequestId(UUID(int=4)))
    assert calls["saved_req"] is True

    processing = ProcessingService(SimpleNamespace(get_by_id=_none, save=_none))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await processing.complete_job(
            job_id, SimpleNamespace(result_type="x", result_id=SimpleNamespace(value=UUID(int=5)))
        )
    with pytest.raises(ValueError):
        await processing.fail_job(job_id, "x")
