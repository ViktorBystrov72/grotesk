from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias, TypedDict

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class AudioSegment(TypedDict):
    start: float
    end: float
    text: str
    speaker: str


class SpeakerSegment(TypedDict):
    speaker: str
    start: float
    end: float


class AudioTranscriptionResult(TypedDict):
    text: str
    language: str
    model_name: str
    speaker_model_name: str
    speaker_count: int
    speakers: list[str]
    segments: list[AudioSegment]
    speaker_segments: list[SpeakerSegment]
    duration_seconds: float


class VideoEditResult(TypedDict):
    output_path: Path
    model_name: str
    operation_count: int
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class JobExecutionResult:
    result_type: str
    artifact_extension: str
    history_payload: JsonObject = field(default_factory=dict)
    artifact_payload: JsonObject | None = None
    artifact_source: Path | None = None

    def __post_init__(self) -> None:
        if self.artifact_payload is None and self.artifact_source is None:
            raise ValueError("Job execution result must include artifact payload or artifact source.")
