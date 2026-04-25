from uuid import UUID

from pydantic import BaseModel, Field


class TimelineOperationRequest(BaseModel):
    start_second: int
    end_second: int
    prompt: str
    reference_asset_id: UUID | None = None


class SubmitTranscriptionRequest(BaseModel):
    media_asset_id: UUID
    model_id: UUID


class SubmitVideoEditingRequest(BaseModel):
    media_asset_id: UUID
    model_id: UUID
    prompt_text: str
    operations: list[TimelineOperationRequest] = Field(default_factory=list)


class PredictResponse(BaseModel):
    job_id: UUID
