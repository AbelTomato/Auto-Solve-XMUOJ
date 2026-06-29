from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from .config import ROOT, load_config
from .models import Problem, Sample
from .parser import parse_problem_detail, parse_problem_detail_api, parse_problem_list, parse_problem_list_api, problem_to_markdown
from .runner import CppRunner
from .solver import Solver
from .utils import ensure_dir, read_json, safe_name, write_json
from .xmuoj_client import XMUOJClient


def paths(contest_id: str) -> dict[str, Path]:
    return {
        "data": ensure_dir(ROOT / "data" / f"contest_{contest_id}"),
        "solutions": ensure_dir(ROOT / "solutions" / f"contest_{contest_id}"),
        "submissions": ensure_dir(ROOT / "submissions" / f"contest_{contest_id}"),
        "build": ensure_dir(ROOT / "build" / f"contest_{contest_id}"),
    }


def load_problems(contest_id: str) -> list[Problem]:
    problem_file = paths(contest_id)["data"] / "problems.json"
    if not problem_file.exists():
        raise RuntimeError(f"缺少 {problem_file}。请先运行：python -m src.main fetch --debug-html")
    raw = read_json(problem_file)
    problems: list[Problem] = []
    for item in raw:
        item = dict(item)
        item["samples"] = [Sample(**s) for s in item.get("samples", [])]
        problems.append(Problem(**item))
    return problems


def filter_problems(problems: list[Problem], selected: list[str]) -> list[Problem]:
    if not selected:
        return problems
    wanted = {x.upper() for x in selected}
    return [p for p in problems if p.index.upper() in wanted or safe_name(p.title).upper() in wanted]


def cmd_fetch(args: argparse.Namespace) -> None:
    cfg = load_config()
    client = XMUOJClient(cfg)
    ps = paths(cfg.contest_id)
    html = client.fetch_contest_page()
    if args.debug_html:
        (ps["data"] / "contest_page.html").write_text(html, encoding="utf-8")
    problems = parse_problem_list(html, cfg.base_url)
    api_problem_details: dict[str, Problem] = {}
    if not problems:
        print("HTML 页面未包含题目链接，尝试通过 API 获取题目列表")
        api_data = client.fetch_contest_problems_api()
        if args.debug_html:
            write_json(ps["data"] / "contest_problems_api.json", api_data)
        problems = parse_problem_list_api(api_data, cfg.base_url, cfg.contest_id)
        for p in problems:
            parsed = parse_problem_detail_api(p, api_data)
            if parsed.statement:
                api_problem_details[p.index] = parsed
    if not problems:
        raise RuntimeError("未解析到题目列表。可能是 Cookie 失效、无权限，或 XMUOJ API 结构变化。请检查 data 目录下的调试文件。")
    problems = filter_problems(problems, args.problems or cfg.problem_filter)
    detailed: list[Problem] = []
    for p in problems:
        if p.index in api_problem_details:
            p = api_problem_details[p.index]
            detailed.append(p)
            (ps["data"] / f"{p.index}.md").write_text(problem_to_markdown(p), encoding="utf-8")
            print(f"FETCHED {p.index}: {p.title} samples={len(p.samples)}")
            continue
        detail_html = client.fetch_problem_page(p.url)
        if args.debug_html:
            (ps["data"] / f"{p.index}_detail.html").write_text(detail_html, encoding="utf-8")
        p = parse_problem_detail(p, detail_html)
        if (not p.statement or len(p.statement) < 200 or not p.samples) and p.problem_id:
            try:
                detail_api = client.fetch_problem_detail_api(p.problem_id)
                if args.debug_html:
                    write_json(ps["data"] / f"{p.index}_detail_api.json", detail_api)
                p = parse_problem_detail_api(p, detail_api)
            except Exception as exc:
                print(f"DETAIL_API_FAILED {p.index}: {exc}")
        detailed.append(p)
        (ps["data"] / f"{p.index}.md").write_text(problem_to_markdown(p), encoding="utf-8")
        print(f"FETCHED {p.index}: {p.title} samples={len(p.samples)}")
    write_json(ps["data"] / "problems.json", detailed)


def cmd_solve(args: argparse.Namespace) -> None:
    cfg = load_config()
    ps = paths(cfg.contest_id)
    problems = filter_problems(load_problems(cfg.contest_id), args.problems or cfg.problem_filter)
    solver = Solver(cfg)
    runner = CppRunner(ps["build"])
    for p in problems:
        source = ps["solutions"] / f"{p.index}.cpp"
        try:
            if source.exists() and not args.force:
                print(f"SKIP {p.index}: solution exists")
            else:
                code = solver.solve(p)
                source.write_text(code + "\n", encoding="utf-8")
                print(f"SOLVED {p.index}: {source}")
            results = runner.run_samples(source, p)
            write_json(ps["solutions"] / f"{p.index}.samples.json", results)
            if results and not all(bool(r["ok"]) for r in results):
                print(f"SAMPLE_FAILED {p.index}")
            else:
                print(f"SAMPLE_OK {p.index} count={len(results)}")
        except Exception as exc:
            write_json(ps["solutions"] / f"{p.index}.error.json", {"problem": asdict(p), "error": str(exc)})
            print(f"SOLVE_FAILED {p.index}: {exc}")
            continue


def cmd_submit(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg.auto_submit and not args.yes:
        raise RuntimeError("AUTO_SUBMIT=false。若确认提交，请设置 AUTO_SUBMIT=true 或传 --yes。")
    ps = paths(cfg.contest_id)
    client = XMUOJClient(cfg)
    runner = CppRunner(ps["build"])
    problems = filter_problems(load_problems(cfg.contest_id), args.problems or cfg.problem_filter)
    submitted = 0
    for p in problems:
        if submitted >= cfg.max_submissions_per_run:
            print("达到 MAX_SUBMISSIONS_PER_RUN，停止提交")
            break
        source = ps["solutions"] / f"{p.index}.cpp"
        if not source.exists():
            print(f"SKIP {p.index}: no solution")
            continue
        sample_results = runner.run_samples(source, p)
        if sample_results and not all(bool(r["ok"]) for r in sample_results):
            write_json(ps["submissions"] / f"{p.index}.blocked_samples.json", sample_results)
            print(f"BLOCKED {p.index}: sample failed")
            continue
        code = source.read_text(encoding="utf-8")
        result = client.submit_code(p.url, code, p.problem_id)
        status = client.poll_recent_status()
        write_json(ps["submissions"] / f"{p.index}.submit.json", {"problem": asdict(p), "submit": result, "status": status})
        submitted += 1
        submission_id = None
        if isinstance(result.get("response"), dict):
            data = result["response"].get("data")
            if isinstance(data, dict):
                submission_id = data.get("submission_id")
        print(f"SUBMITTED {p.index}: {submission_id or result.get('final_url') or result.get('submit_url')}")


def parse_problem_arg(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip().upper() for x in value.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["fetch", "solve", "submit", "all"]:
        p = sub.add_parser(name)
        p.add_argument("--problems", type=parse_problem_arg)
        p.add_argument("--debug-html", action="store_true")
        p.add_argument("--force", action="store_true")
        p.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "solve":
        cmd_solve(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "all":
        cmd_fetch(args)
        cmd_solve(args)
        cmd_submit(args)


if __name__ == "__main__":
    main()