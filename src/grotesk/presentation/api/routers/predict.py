from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from grotesk.application.processing.commands import (
    SubmitTranscriptionJob,
    SubmitVideoEditingJob,
)
from grotesk.domain.catalog.model import ModelId
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.model import MediaAssetId
from grotesk.domain.processing.model import JobId
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.schemas.predict import (
    PredictResponse,
    SubmitTranscriptionRequest,
    SubmitVideoEditingRequest,
)

router = APIRouter()


@router.post("/transcription", response_model=PredictResponse)
async def submit_transcription(
    user_id: UUID,
    request: SubmitTranscriptionRequest,
    application: Annotated[Application, Depends(get_application)],
) -> PredictResponse:
    job_id = JobId(uuid4())
    estimated_cost = Money(Decimal("10.0"))

    command = SubmitTranscriptionJob(
        job_id=job_id,
        user_id=UserId(user_id),
        media_asset_id=MediaAssetId(request.media_asset_id),
        model_id=ModelId(request.model_id),
        estimated_cost=estimated_cost,
    )
    try:
        await application.submit_transcription_job(command)
        return PredictResponse(job_id=job_id.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/video-editing", response_model=PredictResponse)
async def submit_video_editing(
    user_id: UUID,
    request: SubmitVideoEditingRequest,
    application: Annotated[Application, Depends(get_application)],
) -> PredictResponse:
    job_id = JobId(uuid4())
    estimated_cost = Money(Decimal("50.0"))

    command = SubmitVideoEditingJob(
        job_id=job_id,
        user_id=UserId(user_id),
        media_asset_id=MediaAssetId(request.media_asset_id),
        model_id=ModelId(request.model_id),
        estimated_cost=estimated_cost,
    )
    try:
        await application.submit_video_edit_job(command)
        return PredictResponse(job_id=job_id.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
