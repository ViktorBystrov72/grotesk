import tempfile
from pathlib import Path
from typing import Any, cast

import torch
import torch.nn.functional as functional
import torchaudio
from sklearn.cluster import AgglomerativeClustering
from speechbrain.inference.speaker import EncoderClassifier
from transformers import pipeline

from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.types import AudioSegment, AudioTranscriptionResult, SpeakerSegment


class HuggingFaceAudioPipeline:
    def __init__(self, config: MLConfig) -> None:
        self._config = config
        self._asr_pipeline: Any | None = None
        self._speaker_classifier: EncoderClassifier | None = None

    def transcribe(self, source_path: Path, model_id: str) -> AudioTranscriptionResult:
        normalized_path = self._normalize_audio(source_path)
        try:
            asr_pipeline = self._get_asr_pipeline(model_id)
            transcription = cast(
                dict[str, Any],
                asr_pipeline(
                    str(normalized_path),
                    return_timestamps=True,
                    generate_kwargs={"task": "transcribe"},
                ),
            )
            segments = self._build_segments(normalized_path, transcription.get("chunks") or [])
            speaker_segments = self._merge_speaker_segments(segments)
            speakers = sorted(
                {str(segment["speaker"]) for segment in segments if isinstance(segment.get("speaker"), str)}
            )
            duration_values = [
                float(segment["end"]) for segment in speaker_segments if isinstance(segment.get("end"), int | float)
            ]
            return cast(
                AudioTranscriptionResult,
                {
                    "text": str(transcription.get("text", "")).strip(),
                    "language": str(transcription.get("language", "unknown")),
                    "model_name": model_id,
                    "speaker_model_name": self._config.speaker_model_id,
                    "speaker_count": len(speakers),
                    "speakers": speakers,
                    "segments": segments,
                    "speaker_segments": speaker_segments,
                    "duration_seconds": max(duration_values, default=0.0),
                },
            )
        finally:
            if normalized_path != source_path and normalized_path.exists():
                normalized_path.unlink()

    @staticmethod
    def _normalize_audio(source_path: Path) -> Path:
        waveform, sample_rate = torchaudio.load(str(source_path))
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sample_rate != 16000:
            waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
        if waveform.dtype != torch.float32:
            waveform = waveform.to(torch.float32)

        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        normalized_path = Path(handle.name)
        torchaudio.save(str(normalized_path), waveform, 16000)
        return normalized_path

    def _get_asr_pipeline(self, model_id: str) -> Any:
        if self._asr_pipeline is not None and getattr(self._asr_pipeline, "model_id", None) == model_id:
            return self._asr_pipeline

        use_cuda = self._config.device.startswith("cuda") and torch.cuda.is_available()
        device = 0 if use_cuda else -1
        torch_dtype = torch.float16 if use_cuda else torch.float32
        asr_pipeline = pipeline(
            task="automatic-speech-recognition",
            model=model_id,
            chunk_length_s=30,
            device=device,
            torch_dtype=torch_dtype,
        )
        setattr(asr_pipeline, "model_id", model_id)
        self._asr_pipeline = asr_pipeline
        return asr_pipeline

    def _build_segments(
        self,
        source_path: Path,
        transcription_chunks: list[dict[str, Any]],
    ) -> list[AudioSegment]:
        if not transcription_chunks:
            return []

        waveform, sample_rate = torchaudio.load(str(source_path))
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        classifier = self._get_speaker_classifier()
        embeddings: list[list[float]] = []
        prepared_segments: list[AudioSegment] = []
        embedding_indexes: list[int] = []

        for chunk in transcription_chunks:
            timestamp = chunk.get("timestamp") or (None, None)
            start_second = float(timestamp[0] or 0.0)
            end_second = float(timestamp[1] or start_second)
            if end_second <= start_second:
                end_second = start_second + 0.3

            start_frame = max(0, int(start_second * sample_rate))
            end_frame = min(waveform.shape[-1], int(end_second * sample_rate))
            segment_waveform = waveform[:, start_frame:end_frame]
            if segment_waveform.shape[-1] == 0:
                segment_end = min(waveform.shape[-1], start_frame + int(0.5 * sample_rate))
                segment_waveform = waveform[:, start_frame:segment_end]
            if segment_waveform.shape[-1] < int(0.5 * sample_rate):
                padding = int(0.5 * sample_rate) - segment_waveform.shape[-1]
                segment_waveform = functional.pad(segment_waveform, (0, padding))

            prepared_segments.append(
                cast(
                    AudioSegment,
                    {
                        "start": round(start_second, 3),
                        "end": round(end_second, 3),
                        "text": str(chunk.get("text", "")).strip(),
                        "speaker": "unknown",
                    },
                )
            )

            if segment_waveform.shape[-1] == 0:
                continue

            embedding = classifier.encode_batch(segment_waveform.squeeze(0).unsqueeze(0))
            embeddings.append(embedding.squeeze().detach().cpu().tolist())
            embedding_indexes.append(len(prepared_segments) - 1)

        if not embeddings:
            return prepared_segments

        if len(embeddings) == 1:
            prepared_segments[embedding_indexes[0]]["speaker"] = "speaker_01"
            return prepared_segments

        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=0.35,
        )

        labels = clustering.fit_predict(embeddings)
        for prepared_index, label in zip(embedding_indexes, labels, strict=False):
            prepared_segments[prepared_index]["speaker"] = f"speaker_{label + 1:02d}"
        return prepared_segments

    def _get_speaker_classifier(self) -> EncoderClassifier:
        if self._speaker_classifier is not None:
            return self._speaker_classifier

        cache_dir = Path(self._config.artifact_root) / ".speaker-model-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        classifier = EncoderClassifier.from_hparams(
            source=self._config.speaker_model_id,
            savedir=cast(Any, str(cache_dir)),
            run_opts={"device": self._config.device if torch.cuda.is_available() else "cpu"},
        )
        self._speaker_classifier = classifier
        return classifier

    @staticmethod
    def _merge_speaker_segments(segments: list[AudioSegment]) -> list[SpeakerSegment]:
        merged_segments: list[SpeakerSegment] = []
        for segment in segments:
            if not merged_segments or merged_segments[-1]["speaker"] != segment["speaker"]:
                merged_segments.append(
                    cast(
                        SpeakerSegment,
                        {
                            "speaker": segment["speaker"],
                            "start": segment["start"],
                            "end": segment["end"],
                        },
                    )
                )
                continue

            merged_segments[-1]["end"] = segment["end"]
        return merged_segments
