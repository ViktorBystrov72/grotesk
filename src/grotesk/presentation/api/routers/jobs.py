from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.processing.queries import GetUserJobDetails
from grotesk.domain.processing.model import JobId
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application, get_current_user
from grotesk.presentation.api.schemas.jobs import JobDetailResponse, JobHistoryRecordResponse
from grotesk.presentation.helpers import load_json_artifact, resolve_result_artifact_path

router = APIRouter()


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: UUID,
    current_user: Annotated[UserDTO, Depends(get_current_user)],
    application: Annotated[Application, Depends(get_application)],
) -> JobDetailResponse:
    try:
        job = await application.get_user_job_detail(
            GetUserJobDetails(user_id=current_user.user_id, job_id=JobId(job_id))
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    artifact_path = resolve_result_artifact_path(job.result_type, job.result_id)
    artifact_url = f"/jobs/{job.job_id.value}/artifact" if artifact_path is not None else None
    result_payload = load_json_artifact(artifact_path)
    return JobDetailResponse(
        id=job.job_id.value,
        type=job.job_type.value,
        status=job.status.value,
        created_at=job.created_at.isoformat() if job.created_at else "",
        prompt_text=job.prompt_text,
        result_type=job.result_type,
        artifact_url=artifact_url,
        history=[
            JobHistoryRecordResponse(status=record.status.value, message=record.message)
            for record in job.history
        ],
        result=result_payload,
    )


@router.get("/{job_id}/artifact")
async def download_job_artifact(
    job_id: UUID,
    current_user: Annotated[UserDTO, Depends(get_current_user)],
    application: Annotated[Application, Depends(get_application)],
) -> FileResponse:
    try:
        job = await application.get_user_job_detail(
            GetUserJobDetails(user_id=current_user.user_id, job_id=JobId(job_id))
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    artifact_path = resolve_result_artifact_path(job.result_type, job.result_id)
    if artifact_path is None or not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path=artifact_path, filename=artifact_path.name)
