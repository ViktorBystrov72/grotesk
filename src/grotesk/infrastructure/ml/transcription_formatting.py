import json
import re
from typing import Any

_SPEAKER_RE = re.compile(r"speaker_(\d+)")


def format_speaker_name(raw_speaker: str | None) -> str:
    if not raw_speaker:
        return "Спикер"
    match = _SPEAKER_RE.fullmatch(raw_speaker)
    if match:
        return f"Спикер {int(match.group(1))}"
    return raw_speaker.replace("_", " ").title()


def build_transcript_turns(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not result:
        return []
    turns_payload = result.get("turns")
    if isinstance(turns_payload, list):
        normalized_turns: list[dict[str, Any]] = []
        for turn in turns_payload:
            if not isinstance(turn, dict):
                continue
            text = str(turn.get("text", "")).strip()
            if not text:
                continue
            normalized_turns.append(
                {
                    "speaker": format_speaker_name(str(turn.get("speaker", ""))),
                    "text": text,
                }
            )
        if normalized_turns:
            return normalized_turns
    segments = result.get("segments")
    if not isinstance(segments, list):
        return []

    turns: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        speaker = format_speaker_name(str(segment.get("speaker", "")))
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["text"] = f"{turns[-1]['text']} {text}".strip()
            continue
        turns.append(
            {
                "speaker": speaker,
                "text": text,
            }
        )
    return turns


def build_book_transcript(result: dict[str, Any] | None) -> str | None:
    turns = build_transcript_turns(result)
    if turns:
        return "\n\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)
    if not result:
        return None
    text = str(result.get("text", "")).strip()
    return text or None


def prepare_transcription_artifact(result: dict[str, Any]) -> dict[str, Any]:
    turns = build_transcript_turns(result)
    book_transcript = build_book_transcript(result) or ""
    return {
        "text": book_transcript,
        "turns": turns,
        "duration_seconds": result.get("duration_seconds"),
        "model_name": result.get("model_name"),
    }


def dump_json_pretty(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, indent=2)
