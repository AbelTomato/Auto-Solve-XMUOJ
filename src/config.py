from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    base_url: str
    contest_url: str
    cookie: str
    verify_ssl: bool
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    auto_submit: bool
    default_language: str
    problem_filter: List[str]
    max_submissions_per_run: int

    @property
    def contest_id(self) -> str:
        parts = self.contest_url.strip("/").split("/")
        if "contest" in parts:
            i = parts.index("contest")
            if i + 1 < len(parts):
                return parts[i + 1]
        return "unknown"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> Config:
    load_dotenv(ROOT / ".env")
    base_url = os.getenv("XMUOJ_BASE_URL", "https://xmuoj.com").rstrip("/")
    contest_url = os.getenv("XMUOJ_CONTEST_URL", "").strip()
    if not contest_url:
        raise RuntimeError("缺少 XMUOJ_CONTEST_URL")

    full_cookie = os.getenv("XMUOJ_COOKIE", "").strip().strip('"')
    session_id = os.getenv("XMUOJ_SESSION_ID_COOKIE", "").strip().strip('"')
    cookie = full_cookie or (f"PHPSESSID={session_id}" if session_id else "")
    if not cookie:
        raise RuntimeError("缺少 XMUOJ_COOKIE 或 XMUOJ_SESSION_ID_COOKIE")

    problem_filter = [x.strip().upper() for x in os.getenv("PROBLEM_FILTER", "").split(",") if x.strip()]

    return Config(
        base_url=base_url,
        contest_url=contest_url,
        cookie=cookie,
        verify_ssl=_bool(os.getenv("XMUOJ_VERIFY_SSL"), True),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1",
        openai_model=os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini",
        auto_submit=_bool(os.getenv("AUTO_SUBMIT"), False),
        default_language=os.getenv("DEFAULT_LANGUAGE", "cpp").strip().lower(),
        problem_filter=problem_filter,
        max_submissions_per_run=int(os.getenv("MAX_SUBMISSIONS_PER_RUN", "20")),
    )