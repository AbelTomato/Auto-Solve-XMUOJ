from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "item"


def write_json(path: Path, data: Any) -> None:
    def default(o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        raise TypeError(type(o).__name__)

    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=default), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:cpp|c\+\+|cxx)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()