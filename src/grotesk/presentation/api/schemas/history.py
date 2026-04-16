from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: UUID | str
    amount: Decimal
    type: str
    created_at: str


class JobResponse(BaseModel):
    id: UUID
    type: str
    status: str
    created_at: str
