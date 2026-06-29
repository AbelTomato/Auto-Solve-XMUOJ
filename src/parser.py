from __future__ import annotations

import re
from typing import cast
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Problem, Sample


def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()


def _html_to_text(text: str) -> str:
    if "<" not in text or ">" not in text:
        return _clean(text)
    soup = BeautifulSoup(text, "html.parser")
    return _clean(soup.get_text("\n"))


def _extract_section(text: str, start_labels: list[str], end_labels: list[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in start_labels)
    end_pattern = "|".join(re.escape(label) for label in end_labels)
    match = re.search(
        rf"(?:^|\n)\s*(?:{label_pattern})\s*[:：]?\s*\n?(.*?)(?=\n\s*(?:{end_pattern})\s*[:：]?\s*(?:\n|$)|$)",
        text,
        re.I | re.S,
    )
    return _clean(match.group(1)) if match else ""


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first_text(item: dict, keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _alpha_index(pos: int) -> str:
    if pos < 0:
        raise ValueError("pos must be non-negative")
    chars: list[str] = []
    pos += 1
    while pos:
        pos, rem = divmod(pos - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def _problem_items(data: object) -> list[dict]:
    candidates = data.get("data") if isinstance(data, dict) else data
    if isinstance(candidates, dict):
        for key in ["results", "problems", "items", "list"]:
            value = candidates.get(key)
            if isinstance(value, list):
                candidates = value
                break
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict) and item.get("title")]


def parse_problem_list(html: str, base_url: str) -> list[Problem]:
    soup = BeautifulSoup(html, "html.parser")
    problems: list[Problem] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = cast(str, a["href"])
        if not re.search(r"/(problem|problems?)/(\d+)|problem_id=\d+|/contest/\d+/problem", href, re.I):
            continue
        title = _clean(a.get_text(" "))
        if not title or len(title) > 160:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        idx = _alpha_index(len(problems))
        pid_match = re.search(r"(?:problem(?:s)?/|problem_id=)(\d+)", href, re.I)
        problems.append(Problem(index=idx, title=title, url=url, problem_id=pid_match.group(1) if pid_match else None))
    return problems


def parse_problem_list_api(data: object, base_url: str, contest_id: str) -> list[Problem]:
    if isinstance(data, dict) and "please login first" in str(data.get("data", "")).lower():
        raise RuntimeError("XMUOJ 返回 Please login first：Cookie 未生效或已过期，请更新 .env 中的 XMUOJ_COOKIE / XMUOJ_SESSION_ID_COOKIE。")
    problems: list[Problem] = []
    seen: set[str] = set()
    for item in _problem_items(data):
        title = _first_text(item, ["title", "name", "problem_title"])
        raw_id = _first_text(item, ["id", "problem_id", "_id"])
        display_id = _first_text(item, ["display_id", "index", "problem_index"])
        if not title or not (raw_id or display_id):
            continue
        index = (display_id or _alpha_index(len(problems))).upper()
        problem_id = raw_id or display_id
        key = str(problem_id)
        if key in seen:
            continue
        seen.add(key)
        url = urljoin(base_url + "/", f"contest/{contest_id}/problem/{index}")
        problems.append(Problem(index=index, title=title, url=url, problem_id=problem_id))
    return problems


def parse_problem_detail_api(problem: Problem, data: object) -> Problem:
    items = _problem_items(data)
    if items and problem.problem_id:
        matched = [item for item in items if _first_text(item, ["id", "problem_id", "_id"]) == str(problem.problem_id)]
        items = matched or items
    elif not items:
        items = list(_walk(data))
    for item in items:
        title = _first_text(item, ["title", "name", "problem_title"])
        description = _first_text(item, ["description", "statement", "content"])
        if not title and not description:
            continue
        problem.title = title or problem.title
        problem.time_limit = _first_text(item, ["time_limit", "timeLimit"]) or problem.time_limit
        problem.memory_limit = _first_text(item, ["memory_limit", "memoryLimit"]) or problem.memory_limit
        problem.input_description = _html_to_text(_first_text(item, ["input_description", "input", "input_desc"])) or problem.input_description
        problem.output_description = _html_to_text(_first_text(item, ["output_description", "output", "output_desc"])) or problem.output_description
        problem.statement = _clean("\n\n".join(x for x in [_html_to_text(description), problem.input_description, problem.output_description] if x))
        raw_samples = item.get("samples") or item.get("sample") or []
        samples: list[Sample] = []
        if isinstance(raw_samples, list):
            for sample in raw_samples:
                if isinstance(sample, dict):
                    sample_input = _first_text(sample, ["input", "sample_input"])
                    sample_output = _first_text(sample, ["output", "sample_output"])
                    if sample_input or sample_output:
                        samples.append(Sample(input=sample_input, output=sample_output))
        if samples:
            problem.samples = samples
        problem.raw_text = problem.statement
        return problem
    return problem


def parse_problem_detail(problem: Problem, html: str) -> Problem:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    title = soup.find(["h1", "h2", "h3"])
    if title:
        t = _clean(title.get_text(" "))
        if t:
            problem.title = t
    text = _clean(soup.get_text("\n"))
    problem.raw_text = text
    tl = re.search(r"(?:Time Limit|时间限制)\s*[:：]?\s*([^\n]+)", text, re.I)
    ml = re.search(r"(?:Memory Limit|内存限制)\s*[:：]?\s*([^\n]+)", text, re.I)
    if tl:
        problem.time_limit = tl.group(1).strip()
    if ml:
        problem.memory_limit = ml.group(1).strip()
    pres = [pre.get_text("\n").strip("\n") for pre in soup.find_all("pre")]
    samples: list[Sample] = []
    for i in range(0, len(pres) - 1, 2):
        if pres[i].strip() or pres[i + 1].strip():
            samples.append(Sample(input=pres[i], output=pres[i + 1]))
    problem.samples = samples
    problem.statement = text
    section_labels = [
        "题目描述",
        "Description",
        "输入",
        "Input",
        "输出",
        "Output",
        "样例输入",
        "Sample Input",
        "样例输出",
        "Sample Output",
        "提示",
        "Hint",
    ]
    problem.input_description = _extract_section(text, ["输入", "Input"], [x for x in section_labels if x not in {"输入", "Input"}])
    problem.output_description = _extract_section(text, ["输出", "Output"], [x for x in section_labels if x not in {"输出", "Output"}])
    return problem


def problem_to_markdown(problem: Problem) -> str:
    parts = [f"# {problem.index}. {problem.title}", "", f"URL: {problem.url}", ""]
    if problem.time_limit:
        parts.append(f"- 时间限制：{problem.time_limit}")
    if problem.memory_limit:
        parts.append(f"- 内存限制：{problem.memory_limit}")
    if problem.time_limit or problem.memory_limit:
        parts.append("")
    parts += ["## 题面", "", problem.statement, ""]
    if problem.input_description:
        parts += ["## 输入", "", problem.input_description, ""]
    if problem.output_description:
        parts += ["## 输出", "", problem.output_description, ""]
    if problem.samples:
        parts += ["## 样例", ""]
        for i, s in enumerate(problem.samples, 1):
            parts += [f"### 样例 {i} 输入", "", "```", s.input, "```", "", f"### 样例 {i} 输出", "", "```", s.output, "```", ""]
    return "\n".join(parts)