from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from grotesk.application.billing.commands import TopUpBalance
from grotesk.application.billing.queries import GetUserBalance
from grotesk.application.identity_access.dto import UserDTO
from grotesk.domain.billing.model import TransactionId
from grotesk.domain.common.primitives import Money
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application, get_optional_current_user, resolve_user_id
from grotesk.presentation.api.schemas.balance import (
    BalanceResponse,
    TopUpRequestSchema,
    TopUpResponse,
)

router = APIRouter()


@router.get("", response_model=BalanceResponse)
async def get_balance(
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> BalanceResponse:
    resolved_user_id = resolve_user_id(user_id, current_user)
    query = GetUserBalance(user_id=resolved_user_id)
    try:
        balance_str = await application.get_user_balance(query)
        return BalanceResponse(user_id=resolved_user_id.value, balance=Decimal(balance_str))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/top-up", response_model=TopUpResponse)
async def top_up(
    request: TopUpRequestSchema,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> TopUpResponse:
    transaction_id = TransactionId(uuid4())
    resolved_user_id = resolve_user_id(user_id, current_user)
    command = TopUpBalance(
        user_id=resolved_user_id,
        amount=Money(request.amount),
    )
    try:
        await application.top_up_balance(command)
        return TopUpResponse(request_id=transaction_id.value, status="success")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
