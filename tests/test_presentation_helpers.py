from grotesk.infrastructure.ml.transcription_formatting import prepare_transcription_artifact
from grotesk.presentation.filenames import extract_display_filename, extract_original_upload_name
from grotesk.presentation.helpers import build_book_transcript, format_speaker_name


def test_format_speaker_name_humanizes_default_pattern() -> None:
    assert format_speaker_name("speaker_01") == "Спикер 1"


def test_build_book_transcript_renders_readable_dialog() -> None:
    transcript = build_book_transcript(
        {
            "segments": [
                {"speaker": "speaker_01", "text": "Первая реплика"},
                {"speaker": "speaker_02", "text": "Вторая реплика"},
                {"speaker": "speaker_01", "text": "Третья реплика"},
            ]
        }
    )

    assert transcript == ("Спикер 1: Первая реплика\n\nСпикер 2: Вторая реплика\n\nСпикер 1: Третья реплика")


def test_extract_display_filename_hides_plain_uuid_name() -> None:
    assert extract_display_filename("/media/audio/62146b44-e52b-48ec-9b9a-153826b810d9.ogg") is None


def test_extract_display_filename_returns_original_name_from_prefixed_storage_key() -> None:
    assert (
        extract_display_filename("/media/audio/62146b44-e52b-48ec-9b9a-153826b810d9__Ким А.Л.-3.ogg")
        == "Ким А.Л.-3.ogg"
    )


def test_extract_original_upload_name_normalizes_browser_path() -> None:
    assert extract_original_upload_name(r"C:\fakepath\Ким А.Л.-3.ogg") == "Ким А.Л.-3.ogg"


def test_prepare_transcription_artifact_builds_human_readable_json_payload() -> None:
    prepared = prepare_transcription_artifact(
        {
            "text": "Сырой текст",
            "model_name": "openai/whisper-large-v3-turbo",
            "segments": [
                {"speaker": "speaker_01", "text": "Первая реплика", "start": 0.0, "end": 1.0},
                {"speaker": "speaker_01", "text": "Продолжение", "start": 1.0, "end": 2.0},
                {"speaker": "speaker_02", "text": "Ответ", "start": 2.0, "end": 3.0},
            ],
            "duration_seconds": 3.0,
        }
    )

    assert prepared["text"] == "Спикер 1: Первая реплика Продолжение\n\nСпикер 2: Ответ"
    assert prepared["duration_seconds"] == 3.0
    assert prepared["model_name"] == "openai/whisper-large-v3-turbo"
    assert prepared["turns"][0]["text"] == "Первая реплика Продолжение"
