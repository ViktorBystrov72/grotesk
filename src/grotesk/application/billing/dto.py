from dataclasses import dataclass
from datetime import datetime

from grotesk.domain.billing.model import TransactionType
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class BillingTransactionDTO:
    transaction_type: TransactionType
    amount: str
    currency: str
    created_at: datetime
    related_job_id: JobId | None
