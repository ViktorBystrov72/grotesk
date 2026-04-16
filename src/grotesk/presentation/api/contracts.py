from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegisterUserRequest:
    email: str
    password: str


@dataclass(frozen=True)
class UploadMediaRequest:
    media_type: str
    file_name: str
    prompt_attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineOperationRequest:
    start_second: int
    end_second: int
    prompt: str
    reference_asset_id: str | None = None


@dataclass(frozen=True)
class SubmitTranscriptionRequest:
    media_asset_id: str
    model_id: str


@dataclass(frozen=True)
class SubmitVideoEditingRequest:
    media_asset_id: str
    model_id: str
    prompt_text: str
    operations: list[TimelineOperationRequest] = field(default_factory=list)


@dataclass(frozen=True)
class ApproveTopUpRequest:
    request_id: str
