from __future__ import annotations

from uuid import UUID

import pytest

from grotesk.domain.common.primitives import TimestampRange
from grotesk.domain.media_ingestion.model import MediaAssetId
from grotesk.domain.processing.model import JobId
from grotesk.domain.speech.model import SpeakerLabel, SpeakerSegment, Transcript, TranscriptId
from grotesk.domain.video_editing.model import (
    PromptRequest,
    PromptRequestId,
    PromptText,
    TimelineEditOperation,
    VideoEditResult,
    VideoEditResultId,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


def test_speech_model_entities_and_validation() -> None:
    with pytest.raises(ValueError, match="Speaker label cannot be empty."):
        SpeakerLabel("")

    speaker = SpeakerLabel("S1")
    time_range = TimestampRange(start_second=0, end_second=5)
    segment = SpeakerSegment(speaker=speaker, time_range=time_range, text="hello")
    transcript = Transcript(
        id=TranscriptId(_uuid("00000000-0000-0000-0000-000000000001")),
        job_id=JobId(_uuid("00000000-0000-0000-0000-000000000002")),
        text="full transcript",
        segments=[segment],
    )

    assert transcript.segments[0].speaker.value == "S1"
    assert transcript.segments[0].time_range.end_second == 5
    assert transcript.text == "full transcript"


def test_video_editing_model_entities_and_validation() -> None:
    with pytest.raises(ValueError, match="Prompt text cannot be empty."):
        PromptText("   ")

    prompt = PromptText("replace sky with sunset")
    operation = TimelineEditOperation(
        time_range=TimestampRange(start_second=10, end_second=20),
        prompt=prompt,
        reference_asset_id=MediaAssetId(_uuid("00000000-0000-0000-0000-000000000003")),
    )
    request = PromptRequest(
        id=PromptRequestId(_uuid("00000000-0000-0000-0000-000000000004")),
        source_job_id=JobId(_uuid("00000000-0000-0000-0000-000000000005")),
        prompt_text=prompt,
        operations=[operation],
    )
    result = VideoEditResult(
        id=VideoEditResultId(_uuid("00000000-0000-0000-0000-000000000006")),
        job_id=JobId(_uuid("00000000-0000-0000-0000-000000000005")),
        output_asset_id=MediaAssetId(_uuid("00000000-0000-0000-0000-000000000007")),
    )

    assert request.operations[0].prompt.value == "replace sky with sunset"
    assert request.operations[0].reference_asset_id is not None
    assert result.job_id == request.source_job_id
