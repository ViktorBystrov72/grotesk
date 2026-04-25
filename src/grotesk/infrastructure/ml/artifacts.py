import json
import shutil
from pathlib import Path
from uuid import UUID

from grotesk.infrastructure.ml.types import JobExecutionResult


class ResultArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, result_id: UUID, execution_result: JobExecutionResult) -> Path:
        target_dir = self._root / execution_result.result_type
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{result_id}{execution_result.artifact_extension}"

        if execution_result.artifact_payload is not None:
            target_path.write_text(
                json.dumps(execution_result.artifact_payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return target_path

        if execution_result.artifact_source is None:
            raise ValueError("Artifact source must be provided for binary artifacts.")

        shutil.move(str(execution_result.artifact_source), str(target_path))
        return target_path
