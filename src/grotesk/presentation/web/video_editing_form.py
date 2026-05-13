"""Поля формы video-editing: допустимые значения под Lucy/Wan (VAE spatial=16, temporal кадры)."""

from __future__ import annotations

from grotesk.domain.processing.model import VideoEditJobOutput
from grotesk.infrastructure.ml.config import MLConfig

# Ширина и высота кратны 16 — требование пространственного даунсемплинга Wan VAE в Lucy Edit.
VIDEO_WIDTH_OPTIONS: tuple[int, ...] = (256, 320, 384, 448, 512, 576, 640, 704, 768, 832)
VIDEO_HEIGHT_OPTIONS: tuple[int, ...] = (128, 160, 192, 224, 256, 320, 384, 448, 480, 512)

# Число кадров: (N − 1) кратно 4 — временной шаг того же VAE (см. video_pipeline temporal_align).
VIDEO_MAX_FRAMES_OPTIONS: tuple[int, ...] = (5, 9, 13, 17, 21, 25, 29, 33, 41, 49, 57, 65, 73, 81)

VIDEO_FPS_OPTIONS: tuple[int, ...] = (6, 8, 12, 15, 24, 30)

DEFAULT_VIDEO_WIDTH = 320
DEFAULT_VIDEO_HEIGHT = 192
DEFAULT_VIDEO_FPS = 12
DEFAULT_VIDEO_MAX_FRAMES = 9
DEFAULT_GUIDANCE_SCALE = 3.0

SPATIAL_ALIGN = 16
TEMPORAL_FRAME_RULE = 4


def video_form_defaults_from_ml(ml: MLConfig) -> dict[str, int | float]:
    """Значения по умолчанию для полей формы: из env/MLConfig, если попадают в допустимые списки."""
    width = ml.video_width if ml.video_width in VIDEO_WIDTH_OPTIONS else DEFAULT_VIDEO_WIDTH
    height = ml.video_height if ml.video_height in VIDEO_HEIGHT_OPTIONS else DEFAULT_VIDEO_HEIGHT
    fps = ml.video_fps if ml.video_fps in VIDEO_FPS_OPTIONS else DEFAULT_VIDEO_FPS
    max_frames = ml.video_max_frames if ml.video_max_frames in VIDEO_MAX_FRAMES_OPTIONS else DEFAULT_VIDEO_MAX_FRAMES
    guidance = float(ml.video_guidance_scale)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "max_frames": max_frames,
        "guidance_scale": guidance,
    }


def video_form_state_from_submitted(ml: MLConfig, submitted: dict[str, str] | None) -> dict[str, int | float]:
    """Подставляет отправленные строки формы поверх дефолтов (для ре-рендера после ошибки)."""
    state = video_form_defaults_from_ml(ml)
    if not submitted:
        return state
    mapping = {
        "video_width": "width",
        "video_height": "height",
        "video_fps": "fps",
        "video_max_frames": "max_frames",
        "video_guidance_scale": "guidance_scale",
    }
    for form_key, state_key in mapping.items():
        raw = submitted.get(form_key)
        if raw is None or raw == "":
            continue
        try:
            if state_key == "guidance_scale":
                state[state_key] = float(raw)
            else:
                state[state_key] = int(raw)
        except ValueError:
            pass
    return state


def parse_video_output_from_form(
    *,
    video_width: str,
    video_height: str,
    video_fps: str,
    video_max_frames: str,
    video_guidance_scale: str,
) -> VideoEditJobOutput:
    try:
        width = int(video_width)
        height = int(video_height)
        fps = int(video_fps)
        max_frames = int(video_max_frames)
        guidance_scale = float(video_guidance_scale)
    except ValueError as error:
        msg = "Параметры выходного видео должны быть числами."
        raise ValueError(msg) from error

    if width not in VIDEO_WIDTH_OPTIONS:
        msg = f"Ширина {width}px недопустима. Выберите значение из списка (кратно {SPATIAL_ALIGN})."
        raise ValueError(msg)
    if height not in VIDEO_HEIGHT_OPTIONS:
        msg = f"Высота {height}px недопустима. Выберите значение из списка (кратно {SPATIAL_ALIGN})."
        raise ValueError(msg)
    if width % SPATIAL_ALIGN != 0 or height % SPATIAL_ALIGN != 0:
        msg = f"Ширина и высота должны быть кратны {SPATIAL_ALIGN} (требование VAE модели)."
        raise ValueError(msg)
    if fps not in VIDEO_FPS_OPTIONS:
        msg = f"Частота кадров {fps} недопустима. Выберите значение из списка."
        raise ValueError(msg)
    if max_frames not in VIDEO_MAX_FRAMES_OPTIONS:
        msg = (
            f"Максимум кадров {max_frames} недопустим. Нужно число, при котором (кадры − 1) кратно "
            f"{TEMPORAL_FRAME_RULE} — см. список в форме."
        )
        raise ValueError(msg)
    if (max_frames - 1) % TEMPORAL_FRAME_RULE != 0:
        msg = f"Для этой модели (число кадров − 1) должно делиться на {TEMPORAL_FRAME_RULE}."
        raise ValueError(msg)
    if not 1.0 <= guidance_scale <= 20.0:
        msg = "Guidance scale допустим в диапазоне от 1.0 до 20.0."
        raise ValueError(msg)

    return VideoEditJobOutput(
        width=width,
        height=height,
        fps=fps,
        max_frames=max_frames,
        guidance_scale=guidance_scale,
    )


def video_editing_page_context(
    ml: MLConfig,
    submitted: dict[str, str] | None = None,
) -> dict[str, object]:
    """Контекст для шаблона video-editing: списки значений и текущее состояние полей."""
    return {
        "video_width_options": VIDEO_WIDTH_OPTIONS,
        "video_height_options": VIDEO_HEIGHT_OPTIONS,
        "video_fps_options": VIDEO_FPS_OPTIONS,
        "video_max_frames_options": VIDEO_MAX_FRAMES_OPTIONS,
        "spatial_align": SPATIAL_ALIGN,
        "temporal_frame_rule": TEMPORAL_FRAME_RULE,
        "video_form": video_form_state_from_submitted(ml, submitted),
    }
