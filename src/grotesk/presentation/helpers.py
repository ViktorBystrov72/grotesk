import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import UploadFile

from grotesk.application.media_ingestion.commands import UploadMediaAsset
from grotesk.domain.common.primitives import FileLocation
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.transcription_formatting import (
    build_book_transcript,
    build_transcript_turns,
    dump_json_pretty,
    format_speaker_name,
)
from grotesk.main.application import Application
from grotesk.presentation.filenames import extract_original_upload_name

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

__all__ = [
    "build_book_transcript",
    "build_transcript_turns",
    "detect_media_type",
    "dump_json_pretty",
    "format_speaker_name",
    "get_media_storage_root",
    "load_json_artifact",
    "register_uploaded_media",
    "resolve_result_artifact_path",
    "save_upload_file",
]


def get_media_storage_root() -> Path:
    return Path(os.getenv("MEDIA_STORAGE_ROOT", "/tmp/grotesk-media"))


def detect_media_type(filename: str, content_type: str | None = None) -> MediaType:
    suffix = Path(filename).suffix.lower()
    if suffix in AUDIO_EXTENSIONS or (content_type or "").startswith("audio/"):
        return MediaType.AUDIO
    if suffix in VIDEO_EXTENSIONS or (content_type or "").startswith("video/"):
        return MediaType.VIDEO
    if suffix in IMAGE_EXTENSIONS or (content_type or "").startswith("image/"):
        return MediaType.IMAGE
    raise ValueError("Unsupported media type.")


async def save_upload_file(upload_file: UploadFile, media_type: MediaType) -> Path:
    target_root = get_media_storage_root() / str(media_type)
    target_root.mkdir(parents=True, exist_ok=True)
    original_name = extract_original_upload_name(upload_file.filename)
    suffix = Path(original_name or "").suffix or ".bin"
    if original_name:
        target_path = target_root / f"{uuid4()}__{original_name}"
    else:
        target_path = target_root / f"{uuid4()}{suffix.lower()}"
    content = await upload_file.read()
    await asyncio.to_thread(target_path.write_bytes, content)
    await upload_file.close()
    return target_path


def resolve_result_artifact_path(result_type: str | None, result_id: UUID | None) -> Path | None:
    if result_type is None or result_id is None:
        return None

    artifact_root = Path(MLConfig.from_env().artifact_root) / result_type
    matches = sorted(artifact_root.glob(f"{result_id}.*"))
    if not matches:
        return None
    return matches[0]


def load_json_artifact(artifact_path: Path | None) -> dict[str, Any] | None:
    if artifact_path is None or artifact_path.suffix.lower() != ".json" or not artifact_path.exists():
        return None
    return json.loads(artifact_path.read_text(encoding="utf-8"))


async def register_uploaded_media(
    application: Application,
    owner_id: UserId,
    upload_file: UploadFile,
) -> MediaAsset:
    media_type = detect_media_type(upload_file.filename or "upload.bin", upload_file.content_type)
    stored_path = await save_upload_file(upload_file, media_type)
    asset = MediaAsset(
        id=MediaAssetId(uuid4()),
        owner_id=owner_id,
        media_type=media_type,
        location=FileLocation(str(stored_path)),
    )
    return await application.upload_media(UploadMediaAsset(asset=asset))
