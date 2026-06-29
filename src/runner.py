from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .models import Problem
from .utils import ensure_dir


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def normalize_output(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").strip().split("\n")).strip()


class CppRunner:
    def __init__(self, build_dir: Path):
        self.build_dir = ensure_dir(build_dir)

    def compile(self, source: Path) -> Path:
        exe = self.build_dir / (source.stem + ".exe")
        cmd = ["g++", "-std=c++14", "-O2", "-pipe", str(source), "-o", str(exe)]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError("编译失败:\n" + proc.stderr[-4000:])
        return exe

    def run_samples(self, source: Path, problem: Problem) -> list[dict[str, str | bool]]:
        if not problem.samples:
            return []
        exe = self.compile(source)
        results = []
        for i, sample in enumerate(problem.samples, 1):
            try:
                proc = subprocess.run([str(exe)], input=sample.input, text=True, capture_output=True, timeout=5)
            except subprocess.TimeoutExpired as exc:
                results.append({
                    "sample": str(i),
                    "ok": False,
                    "expected": normalize_output(sample.output),
                    "actual": normalize_output(_to_text(exc.stdout)),
                    "stderr": "运行超时",
                })
                continue
            actual = normalize_output(proc.stdout)
            expected = normalize_output(sample.output)
            ok = proc.returncode == 0 and actual == expected
            results.append({
                "sample": str(i),
                "ok": ok,
                "expected": expected,
                "actual": actual,
                "stderr": proc.stderr[-1000:],
            })
        return results