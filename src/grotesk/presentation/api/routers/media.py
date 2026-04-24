from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from grotesk.application.identity_access.dto import UserDTO
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application, get_current_user
from grotesk.presentation.api.schemas.media import MediaUploadResponse
from grotesk.presentation.helpers import register_uploaded_media

router = APIRouter()


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[UserDTO, Depends(get_current_user)],
    application: Annotated[Application, Depends(get_application)],
) -> MediaUploadResponse:
    try:
        saved_asset = await register_uploaded_media(application, current_user.user_id, file)
        return MediaUploadResponse(
            media_asset_id=saved_asset.id.value,
            media_type=saved_asset.media_type,
            status=saved_asset.status,
            storage_key=saved_asset.location.storage_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
