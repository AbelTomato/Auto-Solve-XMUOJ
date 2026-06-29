from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Sample:
    input: str
    output: str


@dataclass
class Problem:
    index: str
    title: str
    url: str
    problem_id: Optional[str] = None
    time_limit: str = ""
    memory_limit: str = ""
    statement: str = ""
    input_description: str = ""
    output_description: str = ""
    samples: List[Sample] = field(default_factory=list)
    raw_text: str = ""