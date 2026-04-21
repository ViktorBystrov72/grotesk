from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TopUpRequestSchema(BaseModel):
    amount: Decimal


class TopUpResponse(BaseModel):
    request_id: UUID
    status: str


class BalanceResponse(BaseModel):
    user_id: UUID
    balance: Decimal
