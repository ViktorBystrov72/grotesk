import re
from pathlib import Path

_UUID_BASENAME_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:\.[^.]+)?$"
)


def extract_original_upload_name(filename: str | None) -> str | None:
    if not filename:
        return None
    normalized = filename.replace("\\", "/").split("/")[-1].strip()
    return normalized or None


def extract_display_filename(storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    basename = Path(storage_key).name
    if "__" in basename:
        prefix, original_name = basename.split("__", maxsplit=1)
        if _UUID_BASENAME_RE.fullmatch(prefix) and original_name.strip():
            return original_name.strip()
    if _UUID_BASENAME_RE.fullmatch(basename):
        return None
    return basename or None
