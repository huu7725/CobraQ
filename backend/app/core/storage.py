"""Resolve user question files without allowing IDs to become filesystem paths."""
import re
from pathlib import Path
from fastapi import HTTPException


def question_path(folder: Path, file_id: str) -> Path:
    if not re.fullmatch(r"[\w-]{1,128}", file_id) or file_id in {"history", "files_index"}:
        raise HTTPException(400, "Mã đề không hợp lệ")
    return folder / f"{file_id}.json"
