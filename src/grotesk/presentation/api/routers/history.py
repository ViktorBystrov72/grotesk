from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from grotesk.application.billing.queries import GetUserTransactionHistory
from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.processing.queries import GetUserJobHistory
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application, get_optional_current_user, resolve_user_id
from grotesk.presentation.api.schemas.history import JobResponse, TransactionResponse

router = APIRouter()


@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> list[TransactionResponse]:
    resolved_user_id = resolve_user_id(user_id, current_user)
    query = GetUserTransactionHistory(user_id=resolved_user_id)
    try:
        transactions = await application.get_user_transaction_history(query)
        return [
            TransactionResponse(
                id=t.related_job_id.value if t.related_job_id is not None else "top-up",
                amount=Decimal(t.amount),
                type=t.transaction_type.value,
                created_at=t.created_at.isoformat(),
            )
            for t in transactions
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests", response_model=list[JobResponse])
async def get_requests(
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> list[JobResponse]:
    query = GetUserJobHistory(user_id=resolve_user_id(user_id, current_user))
    try:
        jobs = await application.get_user_job_history(query)
        return [
            JobResponse(
                id=job.job_id.value,
                type=job.job_type.value,
                status=job.status.value,
                created_at=job.created_at.isoformat() if job.created_at else "",
            )
            for job in jobs
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
