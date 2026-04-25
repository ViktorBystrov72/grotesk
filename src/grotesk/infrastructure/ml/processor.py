import asyncio
from pathlib import Path
from typing import Protocol

from grotesk.domain.catalog.model import ModelProfile
from grotesk.domain.media_ingestion.model import MediaAsset
from grotesk.domain.processing.model import JobType, ProcessingJob
from grotesk.infrastructure.ml.audio_pipeline import HuggingFaceAudioPipeline
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.transcription_formatting import prepare_transcription_artifact
from grotesk.infrastructure.ml.types import AudioTranscriptionResult, JobExecutionResult, VideoEditResult
from grotesk.infrastructure.ml.video_pipeline import HuggingFaceVideoPipeline


class JobProcessor(Protocol):
    async def process(
        self,
        job: ProcessingJob,
        media_asset: MediaAsset,
        model_profile: ModelProfile,
    ) -> JobExecutionResult:
        raise NotImplementedError


class HuggingFaceJobProcessor:
    def __init__(self, config: MLConfig) -> None:
        self._config = config
        self._audio_pipeline = HuggingFaceAudioPipeline(config)
        self._video_pipeline = HuggingFaceVideoPipeline(config)

    async def process(
        self,
        job: ProcessingJob,
        media_asset: MediaAsset,
        model_profile: ModelProfile,
    ) -> JobExecutionResult:
        source_path = self._resolve_media_path(media_asset.location.storage_key)
        if not source_path.exists():
            raise FileNotFoundError(f"Media file does not exist: {source_path}")

        if job.job_type == JobType.TRANSCRIPTION:
            model_id = model_profile.name or self._config.audio_model_id
            transcription_result: AudioTranscriptionResult = await asyncio.to_thread(
                self._audio_pipeline.transcribe,
                source_path,
                model_id,
            )
            return JobExecutionResult(
                result_type="transcription",
                artifact_extension=".json",
                artifact_payload=prepare_transcription_artifact(transcription_result),
                history_payload={
                    "model_name": model_id,
                    "speaker_count": transcription_result.get("speaker_count", 0),
                    "text_preview": str(transcription_result.get("text", ""))[:160],
                },
            )

        if job.job_type == JobType.VIDEO_EDITING:
            model_id = model_profile.name or self._config.video_model_id
            video_result: VideoEditResult = await asyncio.to_thread(
                self._video_pipeline.edit,
                source_path,
                model_id,
                job.prompt_text,
                job.operations,
            )
            return JobExecutionResult(
                result_type="video_editing",
                artifact_extension=".mp4",
                artifact_source=video_result["output_path"],
                history_payload={
                    "model_name": model_id,
                    "operation_count": video_result["operation_count"],
                    "width": video_result["width"],
                    "height": video_result["height"],
                    "fps": video_result["fps"],
                },
            )

        raise ValueError(f"Unsupported job type: {job.job_type.value}")

    def _resolve_media_path(self, storage_key: str) -> Path:
        storage_path = Path(storage_key)
        if storage_path.is_absolute():
            return storage_path
        return Path(self._config.media_storage_root) / storage_path
