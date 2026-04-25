import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, cast

import soundfile as sf
import torch
import torch.nn.functional as functional
from silero_vad import get_speech_timestamps, load_silero_vad
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
        self._vad_model: Any | None = None

    def transcribe(self, source_path: Path, model_id: str) -> AudioTranscriptionResult:
        normalized_path = self._normalize_audio(source_path)
        try:
            asr_pipeline = self._get_asr_pipeline(model_id)
            waveform, sample_rate = self._load_waveform(normalized_path)
            transcription = cast(
                dict[str, Any],
                asr_pipeline(
                    {"raw": waveform.squeeze(0).cpu().numpy(), "sampling_rate": sample_rate},
                    return_timestamps=True,
                    generate_kwargs={"task": "transcribe", "language": "russian"},
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
                    "language": "russian",
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
    def _load_waveform(path: Path) -> tuple[torch.Tensor, int]:
        data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        return waveform, int(sample_rate)

    def _normalize_audio(self, source_path: Path) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        normalized_path = Path(handle.name)
        self._run_command(
            [
                self._config.ffmpeg_binary,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_f32le",
                str(normalized_path),
            ]
        )
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

        waveform, sample_rate = self._load_waveform(source_path)
        diarization_segments = self._build_diarization_segments(waveform, sample_rate)
        prepared_segments: list[AudioSegment] = []

        for chunk in transcription_chunks:
            timestamp = chunk.get("timestamp") or (None, None)
            start_second = float(timestamp[0] or 0.0)
            end_second = float(timestamp[1] or start_second)
            if end_second <= start_second:
                end_second = start_second + 0.3

            prepared_segments.append(
                cast(
                    AudioSegment,
                    {
                        "start": round(start_second, 3),
                        "end": round(end_second, 3),
                        "text": str(chunk.get("text", "")).strip(),
                        "speaker": self._assign_speaker(start_second, end_second, diarization_segments),
                    },
                )
            )

        return prepared_segments

    def _build_diarization_segments(self, waveform: torch.Tensor, sample_rate: int) -> list[SpeakerSegment]:
        speech_regions = self._detect_speech_regions(waveform, sample_rate)
        if not speech_regions:
            return []

        classifier = self._get_speaker_classifier()
        embeddings: list[list[float]] = []
        diarization_segments: list[SpeakerSegment] = []

        for start_frame, end_frame in speech_regions:
            segment_waveform = waveform[:, start_frame:end_frame]
            if segment_waveform.shape[-1] == 0:
                continue
            min_frames = int(0.8 * sample_rate)
            if segment_waveform.shape[-1] < min_frames:
                padding = min_frames - segment_waveform.shape[-1]
                segment_waveform = functional.pad(segment_waveform, (0, padding))

            embedding = classifier.encode_batch(segment_waveform.squeeze(0).unsqueeze(0))
            embeddings.append(embedding.squeeze().detach().cpu().tolist())
            diarization_segments.append(
                cast(
                    SpeakerSegment,
                    {
                        "speaker": "unknown",
                        "start": round(start_frame / sample_rate, 3),
                        "end": round(end_frame / sample_rate, 3),
                    },
                )
            )

        if not diarization_segments:
            return []

        if len(diarization_segments) == 1:
            diarization_segments[0]["speaker"] = "speaker_01"
            return diarization_segments

        durations = [float(segment["end"]) - float(segment["start"]) for segment in diarization_segments]
        labels = self._cluster_speaker_embeddings(embeddings, durations)
        for diarization_segment, label in zip(diarization_segments, labels, strict=False):
            diarization_segment["speaker"] = f"speaker_{label + 1:02d}"
        return self._merge_short_turns(self._merge_speaker_segments_from_regions(diarization_segments))

    def _cluster_speaker_embeddings(self, embeddings: list[list[float]], durations: list[float]) -> list[int]:
        if len(embeddings) == 1:
            return [0]

        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=0.14,
        )
        labels = clustering.fit_predict(embeddings).tolist()
        labels = self._reduce_cluster_count(labels, embeddings, durations)
        labels = self._collapse_to_dominant_speakers(labels, embeddings, durations)
        labels = self._reduce_sparse_clusters(labels, embeddings, durations)
        return self._reindex_labels(labels)

    def _detect_speech_regions(self, waveform: torch.Tensor, sample_rate: int) -> list[tuple[int, int]]:
        vad_model = self._get_vad_model()
        speech_timestamps = get_speech_timestamps(
            waveform.squeeze(0).cpu(),
            vad_model,
            sampling_rate=sample_rate,
            min_speech_duration_ms=400,
            min_silence_duration_ms=450,
            speech_pad_ms=120,
            return_seconds=False,
        )
        max_region_frames = int(sample_rate * 12.0)
        chunked_regions: list[tuple[int, int]] = []
        for speech_timestamp in speech_timestamps:
            start = int(speech_timestamp["start"])
            end = int(speech_timestamp["end"])
            while end - start > max_region_frames:
                chunked_regions.append((start, start + max_region_frames))
                start += max_region_frames
            chunked_regions.append((start, end))
        return chunked_regions

    @staticmethod
    def _merge_speaker_segments_from_regions(segments: list[SpeakerSegment]) -> list[SpeakerSegment]:
        merged_segments: list[SpeakerSegment] = []
        for segment in segments:
            if not merged_segments:
                merged_segments.append(segment)
                continue
            previous_segment = merged_segments[-1]
            gap = float(segment["start"]) - float(previous_segment["end"])
            if previous_segment["speaker"] == segment["speaker"] and gap <= 0.35:
                previous_segment["end"] = segment["end"]
                continue
            merged_segments.append(segment)
        return merged_segments

    def _merge_short_turns(self, segments: list[SpeakerSegment]) -> list[SpeakerSegment]:
        if len(segments) < 3:
            return segments
        stabilized_segments = [cast(SpeakerSegment, dict(segment)) for segment in segments]
        for index in range(1, len(stabilized_segments) - 1):
            current_segment = stabilized_segments[index]
            current_duration = float(current_segment["end"]) - float(current_segment["start"])
            previous_segment = stabilized_segments[index - 1]
            next_segment = stabilized_segments[index + 1]
            if (
                current_duration < self._config.audio_short_turn_seconds
                and previous_segment["speaker"] == next_segment["speaker"]
                and current_segment["speaker"] != previous_segment["speaker"]
            ):
                current_segment["speaker"] = previous_segment["speaker"]
                continue
            previous_duration = float(previous_segment["end"]) - float(previous_segment["start"])
            next_duration = float(next_segment["end"]) - float(next_segment["start"])
            if current_duration < 0.9 and current_segment["speaker"] != previous_segment["speaker"]:
                if previous_duration >= next_duration and previous_duration > 2.4:
                    current_segment["speaker"] = previous_segment["speaker"]
                    continue
                if next_duration > previous_duration and next_duration > 2.4:
                    current_segment["speaker"] = next_segment["speaker"]
        return HuggingFaceAudioPipeline._merge_speaker_segments_from_regions(stabilized_segments)

    def _reduce_cluster_count(
        self,
        labels: list[int],
        embeddings: list[list[float]],
        durations: list[float],
    ) -> list[int]:
        max_speakers = max(1, self._config.audio_max_speakers)
        label_durations = self._compute_label_durations(labels, durations)
        if len(label_durations) <= max_speakers:
            return labels

        ranked_labels = sorted(label_durations.items(), key=lambda item: item[1], reverse=True)
        keep_labels = [label for label, _duration in ranked_labels[:max_speakers]]
        return self._remap_to_nearest_labels(labels, embeddings, keep_labels)

    def _collapse_to_dominant_speakers(
        self,
        labels: list[int],
        embeddings: list[list[float]],
        durations: list[float],
    ) -> list[int]:
        label_durations = self._compute_label_durations(labels, durations)
        if len(label_durations) <= 1:
            return labels

        total_duration = sum(label_durations.values())
        if total_duration <= 0:
            return labels

        ranked_labels = sorted(label_durations.items(), key=lambda item: item[1], reverse=True)
        dominant_label, dominant_duration = ranked_labels[0]
        dominant_ratio = dominant_duration / total_duration
        secondary_ratio = ranked_labels[1][1] / total_duration if len(ranked_labels) > 1 else 0.0

        if dominant_ratio < self._config.audio_dominant_speaker_ratio:
            return labels

        if secondary_ratio < self._config.audio_secondary_speaker_ratio:
            return [dominant_label for _label in labels]

        keep_labels = [dominant_label, ranked_labels[1][0]]
        return self._remap_to_nearest_labels(labels, embeddings, keep_labels)

    def _reduce_sparse_clusters(
        self,
        labels: list[int],
        embeddings: list[list[float]],
        durations: list[float],
    ) -> list[int]:
        label_durations = self._compute_label_durations(labels, durations)
        label_counts = Counter(labels)
        keep_labels = [
            label for label, duration in label_durations.items() if duration >= 2.5 or label_counts[label] >= 2
        ]
        if not keep_labels:
            dominant_label = max(label_durations, key=label_durations.get)
            return [dominant_label for _label in labels]
        if len(keep_labels) == len(label_durations):
            return labels
        return self._remap_to_nearest_labels(labels, embeddings, keep_labels)

    @staticmethod
    def _compute_label_durations(labels: list[int], durations: list[float]) -> dict[int, float]:
        label_durations: dict[int, float] = {}
        for label, duration in zip(labels, durations, strict=False):
            label_durations[label] = label_durations.get(label, 0.0) + duration
        return label_durations

    @staticmethod
    def _compute_label_centroids(labels: list[int], embeddings: list[list[float]]) -> dict[int, torch.Tensor]:
        grouped_embeddings: dict[int, list[torch.Tensor]] = {}
        for label, embedding in zip(labels, embeddings, strict=False):
            grouped_embeddings.setdefault(label, []).append(torch.tensor(embedding, dtype=torch.float32))
        centroids: dict[int, torch.Tensor] = {}
        for label, vectors in grouped_embeddings.items():
            centroid = torch.stack(vectors, dim=0).mean(dim=0)
            centroids[label] = functional.normalize(centroid, dim=0)
        return centroids

    def _remap_to_nearest_labels(
        self,
        labels: list[int],
        embeddings: list[list[float]],
        keep_labels: list[int],
    ) -> list[int]:
        if not keep_labels:
            return labels
        centroids = self._compute_label_centroids(labels, embeddings)
        normalized_keep_labels = [label for label in keep_labels if label in centroids]
        if not normalized_keep_labels:
            return labels

        remapped_labels: list[int] = []
        for label, embedding in zip(labels, embeddings, strict=False):
            if label in normalized_keep_labels:
                remapped_labels.append(label)
                continue
            vector = functional.normalize(torch.tensor(embedding, dtype=torch.float32), dim=0)
            closest_label = max(
                normalized_keep_labels,
                key=lambda candidate: float(torch.dot(vector, centroids[candidate])),
            )
            remapped_labels.append(closest_label)
        return remapped_labels

    @staticmethod
    def _reindex_labels(labels: list[int]) -> list[int]:
        label_map: dict[int, int] = {}
        next_label = 0
        normalized_labels: list[int] = []
        for label in labels:
            if label not in label_map:
                label_map[label] = next_label
                next_label += 1
            normalized_labels.append(label_map[label])
        return normalized_labels

    @staticmethod
    def _assign_speaker(start_second: float, end_second: float, diarization_segments: list[SpeakerSegment]) -> str:
        if not diarization_segments:
            return "speaker_01"

        best_speaker = "speaker_01"
        best_overlap = 0.0
        for segment in diarization_segments:
            overlap = max(
                0.0,
                min(end_second, float(segment["end"])) - max(start_second, float(segment["start"])),
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = str(segment["speaker"])
        if best_overlap > 0:
            return best_speaker

        chunk_center = (start_second + end_second) / 2
        nearest_segment = min(
            diarization_segments,
            key=lambda segment: abs((float(segment["start"]) + float(segment["end"])) / 2 - chunk_center),
        )
        return str(nearest_segment["speaker"])

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

    def _get_vad_model(self) -> Any:
        if self._vad_model is not None:
            return self._vad_model
        self._vad_model = load_silero_vad()
        return self._vad_model

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

    @staticmethod
    def _run_command(command: list[str]) -> None:
        completed_process = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed_process.returncode != 0:
            raise RuntimeError(completed_process.stderr.strip() or "ffmpeg command failed")
