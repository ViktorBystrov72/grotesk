from typing import Any
from uuid import UUID

from pydantic import BaseModel


class JobHistoryRecordResponse(BaseModel):
    status: str
    message: str


class JobDetailResponse(BaseModel):
    id: UUID
    type: str
    status: str
    created_at: str
    prompt_text: str | None
    result_type: str | None
    artifact_url: str | None
    history: list[JobHistoryRecordResponse]
    result: dict[str, Any] | None = None
