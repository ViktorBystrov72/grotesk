from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.processing.commands import (
    SubmitTranscriptionJob,
    SubmitVideoEditingJob,
)
from grotesk.domain.catalog.model import ModelId
from grotesk.domain.common.primitives import Money
from grotesk.domain.media_ingestion.model import MediaAssetId
from grotesk.domain.processing.model import JobId, TimelineOperation
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application, get_optional_current_user, resolve_user_id
from grotesk.presentation.api.schemas.predict import (
    PredictResponse,
    SubmitTranscriptionRequest,
    SubmitVideoEditingRequest,
)

router = APIRouter()


@router.post("/transcription", response_model=PredictResponse)
async def submit_transcription(
    request: SubmitTranscriptionRequest,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> PredictResponse:
    job_id = JobId(uuid4())
    estimated_cost = Money(Decimal("10.0"))
    resolved_user_id = resolve_user_id(user_id, current_user)

    command = SubmitTranscriptionJob(
        job_id=job_id,
        user_id=resolved_user_id,
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
    request: SubmitVideoEditingRequest,
    application: Annotated[Application, Depends(get_application)],
    current_user: Annotated[UserDTO | None, Depends(get_optional_current_user)],
    user_id: UUID | None = None,
) -> PredictResponse:
    job_id = JobId(uuid4())
    estimated_cost = Money(Decimal("50.0"))
    resolved_user_id = resolve_user_id(user_id, current_user)

    command = SubmitVideoEditingJob(
        job_id=job_id,
        user_id=resolved_user_id,
        media_asset_id=MediaAssetId(request.media_asset_id),
        model_id=ModelId(request.model_id),
        estimated_cost=estimated_cost,
        prompt_text=request.prompt_text,
        operations=[
            TimelineOperation(
                start_second=operation.start_second,
                end_second=operation.end_second,
                prompt=operation.prompt,
                reference_asset_id=MediaAssetId(operation.reference_asset_id) if operation.reference_asset_id else None,
            )
            for operation in request.operations
        ],
    )
    try:
        await application.submit_video_edit_job(command)
        return PredictResponse(job_id=job_id.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
