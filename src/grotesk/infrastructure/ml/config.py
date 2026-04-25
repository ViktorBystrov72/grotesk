import os
from dataclasses import dataclass

DEFAULT_AUDIO_MODEL_ID = "openai/whisper-large-v3-turbo"
DEFAULT_SPEAKER_MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
DEFAULT_VIDEO_MODEL_ID = "decart-ai/Lucy-Edit-Dev"


@dataclass(frozen=True)
class MLConfig:
    media_storage_root: str
    artifact_root: str
    audio_model_id: str
    speaker_model_id: str
    audio_max_speakers: int
    audio_dominant_speaker_ratio: float
    audio_secondary_speaker_ratio: float
    audio_short_turn_seconds: float
    video_model_id: str
    device: str
    video_width: int
    video_height: int
    video_fps: int
    video_max_frames: int
    video_guidance_scale: float
    ffmpeg_binary: str
    ffprobe_binary: str

    @classmethod
    def from_env(cls) -> "MLConfig":
        media_storage_root = os.getenv("MEDIA_STORAGE_ROOT", "/tmp/grotesk-media")
        artifact_root = os.getenv("RESULT_ARTIFACT_ROOT", os.path.join(media_storage_root, "results"))
        return cls(
            media_storage_root=media_storage_root,
            artifact_root=artifact_root,
            audio_model_id=os.getenv("HF_AUDIO_MODEL_ID", DEFAULT_AUDIO_MODEL_ID),
            speaker_model_id=os.getenv("HF_SPEAKER_MODEL_ID", DEFAULT_SPEAKER_MODEL_ID),
            audio_max_speakers=int(os.getenv("HF_AUDIO_MAX_SPEAKERS", "3")),
            audio_dominant_speaker_ratio=float(os.getenv("HF_AUDIO_DOMINANT_SPEAKER_RATIO", "0.72")),
            audio_secondary_speaker_ratio=float(os.getenv("HF_AUDIO_SECONDARY_SPEAKER_RATIO", "0.18")),
            audio_short_turn_seconds=float(os.getenv("HF_AUDIO_SHORT_TURN_SECONDS", "1.8")),
            video_model_id=os.getenv("HF_VIDEO_MODEL_ID", DEFAULT_VIDEO_MODEL_ID),
            device=os.getenv("HF_DEVICE", "cpu"),
            video_width=int(os.getenv("HF_VIDEO_WIDTH", "832")),
            video_height=int(os.getenv("HF_VIDEO_HEIGHT", "480")),
            video_fps=int(os.getenv("HF_VIDEO_FPS", "24")),
            video_max_frames=int(os.getenv("HF_VIDEO_MAX_FRAMES", "81")),
            video_guidance_scale=float(os.getenv("HF_VIDEO_GUIDANCE_SCALE", "5.0")),
            ffmpeg_binary=os.getenv("FFMPEG_BINARY", "ffmpeg"),
            ffprobe_binary=os.getenv("FFPROBE_BINARY", "ffprobe"),
        )
