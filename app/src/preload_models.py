import logging
import os
import shutil
import time
from pathlib import Path

from huggingface_hub import snapshot_download

from grotesk.infrastructure.ml.config import MLConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def preload_step(title: str, callback) -> None:
    started_at = time.perf_counter()
    logger.info("Preloading %s...", title)
    callback()
    elapsed_seconds = time.perf_counter() - started_at
    logger.info("Finished %s in %.2fs", title, elapsed_seconds)


def download_hf_repo(repo_id: str, token: str | None) -> None:
    snapshot_download(
        repo_id=repo_id,
        token=token,
        max_workers=4,
    )


def download_speechbrain_repo(repo_id: str, token: str | None, target_dir: str) -> None:
    target_path = Path(target_dir)
    required_files = {
        "hyperparams.yaml",
        "embedding_model.ckpt",
        "mean_var_norm_emb.ckpt",
        "classifier.ckpt",
        "label_encoder.txt",
    }
    existing_files = {path.name for path in target_path.iterdir()} if target_path.exists() else set()
    if required_files.issubset(existing_files):
        logger.info("SpeechBrain cache already prepared at %s", target_dir)
        return

    if target_path.exists():
        shutil.rmtree(target_path)
    target_path.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=repo_id,
        token=token,
        local_dir=target_dir,
        max_workers=4,
    )


def main() -> None:
    config = MLConfig.from_env()
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN") or os.getenv("HF_TOK")
    model_cache_root = os.getenv("HF_HOME", "/models/hf")
    logger.info("Using model cache root: %s", model_cache_root)
    logger.info("Using HF_HOME: %s", os.getenv("HF_HOME", ""))
    logger.info("Using TORCH_HOME: %s", os.getenv("TORCH_HOME", ""))

    preload_step(
        f"ASR model {config.audio_model_id}",
        lambda: download_hf_repo(config.audio_model_id, hf_token),
    )
    preload_step(
        f"speaker model {config.speaker_model_id}",
        lambda: download_speechbrain_repo(
            config.speaker_model_id,
            hf_token,
            os.path.join(model_cache_root, "speechbrain"),
        ),
    )
    preload_step(
        f"video model {config.video_model_id}",
        lambda: download_hf_repo(config.video_model_id, hf_token),
    )


if __name__ == "__main__":
    main()
