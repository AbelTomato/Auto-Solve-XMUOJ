from __future__ import annotations

import re
import time
import urllib3
from typing import Any, cast
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import Config


class XMUOJClient:
    def __init__(self, config: Config):
        self.config = config
        if not config.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 Auto-Solving-XMUOJ/0.1",
            "Cookie": config.cookie,
            "Referer": config.base_url + "/",
        })
        csrf = self._csrf_token()
        if csrf:
            self.session.headers.update({"X-CSRFToken": csrf})

    def _csrf_token(self) -> str:
        match = re.search(r"(?:^|;\s*)csrftoken=([^;]+)", self.config.cookie)
        return match.group(1) if match else ""

    def get(self, url: str) -> requests.Response:
        r = self.session.get(url, timeout=30, verify=self.config.verify_ssl)
        r.raise_for_status()
        return r

    def post(self, url: str, data: dict[str, Any]) -> requests.Response:
        r = self.session.post(url, data=data, timeout=30, verify=self.config.verify_ssl)
        r.raise_for_status()
        return r

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        url = urljoin(self.config.base_url + "/", path.lstrip("/"))
        r = self.session.post(url, json=payload, timeout=30, verify=self.config.verify_ssl)
        r.raise_for_status()
        return r.json()

    def get_json(self, path: str, params: dict[str, Any]) -> Any:
        url = urljoin(self.config.base_url + "/", path.lstrip("/"))
        r = self.session.get(url, params=params, timeout=30, verify=self.config.verify_ssl)
        r.raise_for_status()
        return r.json()

    def fetch_contest_page(self) -> str:
        return self.get(self.config.contest_url).text

    def fetch_problem_page(self, url: str) -> str:
        return self.get(url).text

    def fetch_contest_problems_api(self) -> Any:
        errors: list[str] = []
        for path in ["/api/contest/problem", "/api/contest/problems", "/api/problem"]:
            try:
                return self.get_json(path, {"contest_id": self.config.contest_id})
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        raise RuntimeError("无法通过已知 API 获取题目列表：" + " | ".join(errors))

    def fetch_problem_detail_api(self, problem_id: str) -> Any:
        errors: list[str] = []
        for path in ["/api/contest/problem", "/api/problem"]:
            for key in ["problem_id", "id"]:
                try:
                    return self.get_json(path, {"contest_id": self.config.contest_id, key: problem_id})
                except Exception as exc:
                    errors.append(f"{path}?{key}=...: {exc}")
        raise RuntimeError("无法通过已知 API 获取题目详情：" + " | ".join(errors))

    def infer_submit_form(self, problem_url: str) -> tuple[str, dict[str, str], dict[str, str]]:
        html = self.fetch_problem_page(problem_url)
        soup = BeautifulSoup(html, "html.parser")
        best = None
        for form in soup.find_all("form"):
            text = str(form).lower()
            if "source" in text or "code" in text or "submit" in text or "language" in text:
                best = form
                break
        if best is None:
            raise RuntimeError(f"未能在页面推断提交表单：{problem_url}")
        submit_url = urljoin(problem_url, cast(str, best.get("action") or problem_url))
        fields: dict[str, str] = {}
        options: dict[str, str] = {}
        for inp in best.find_all(["input", "textarea", "select"]):
            name = cast(str | None, inp.get("name"))
            if not name:
                continue
            fields[name] = cast(str, inp.get("value", ""))
            if inp.name == "select":
                for opt in inp.find_all("option"):
                    label = opt.get_text(" ").strip().lower()
                    value = cast(str, opt.get("value", ""))
                    if value:
                        options[label] = value
        return submit_url, fields, options

    def choose_language_value(self, options: dict[str, str], default_language: str) -> str:
        if not options:
            return "0"
        candidates = ["gnu c++", "g++", "c++14", "c++11", "c++", "cpp"] if default_language == "cpp" else [default_language]
        for cand in candidates:
            for label, value in options.items():
                if cand in label:
                    return value
        return next(iter(options.values()))

    def api_language_value(self) -> str:
        if self.config.default_language == "cpp":
            return "C++"
        return self.config.default_language

    def submit_code_api(self, problem_id: str, code: str) -> dict[str, Any]:
        if not problem_id:
            raise RuntimeError("缺少 problem_id，无法使用 API 提交")
        payload = {
            "problem_id": problem_id,
            "contest_id": self.config.contest_id,
            "language": self.api_language_value(),
            "code": code,
        }
        errors: list[str] = []
        for path in ["/api/submission/", "/api/submission"]:
            try:
                data = self.post_json(path, payload)
                if isinstance(data, dict) and data.get("error"):
                    raise RuntimeError(f"{data.get('error')}: {data.get('data')}")
                return {"method": "api", "submit_url": urljoin(self.config.base_url + "/", path.lstrip("/")), "payload": {**payload, "code": "<omitted>"}, "response": data}
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        raise RuntimeError("API 提交失败：" + " | ".join(errors))

    def submit_code(self, problem_url: str, code: str, problem_id: str | None = None) -> dict[str, Any]:
        form_error = ""
        try:
            return self.submit_code_form(problem_url, code)
        except Exception as exc:
            form_error = str(exc)
        try:
            result = self.submit_code_api(problem_id or "", code)
            result["form_error"] = form_error
            return result
        except Exception as exc:
            raise RuntimeError(f"表单提交失败：{form_error}\nAPI 提交失败：{exc}") from exc

    def submit_code_form(self, problem_url: str, code: str) -> dict[str, Any]:
        submit_url, fields, options = self.infer_submit_form(problem_url)
        data = dict(fields)
        lang_value = self.choose_language_value(options, self.config.default_language)
        language_keys = [k for k in data if re.search(r"lang|language|compiler", k, re.I)] or ["language"]
        code_keys = [k for k in data if re.search(r"source|code|text", k, re.I)] or ["source"]
        data[language_keys[0]] = lang_value
        data[code_keys[0]] = code
        resp = self.post(submit_url, data)
        return {"method": "form", "submit_url": submit_url, "status_code": resp.status_code, "final_url": resp.url, "text_head": resp.text[:1000]}

    def poll_recent_status(self, delay: float = 2.0, attempts: int = 10) -> list[dict[str, str]]:
        status_url = urljoin(self.config.base_url + "/", "status")
        results: list[dict[str, str]] = []
        for _ in range(attempts):
            time.sleep(delay)
            try:
                html = self.get(status_url).text
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")[:5]
            results = [{"text": " ".join(row.get_text(" ").split())} for row in rows]
            if any(x.get("text") and not re.search(r"pending|judging|等待|评测中", x["text"], re.I) for x in results):
                break
        return results