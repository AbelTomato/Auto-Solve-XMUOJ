from __future__ import annotations

from openai import OpenAI

from .config import Config
from .models import Problem
from .utils import strip_code_fence


SYSTEM_PROMPT = """你是算法竞赛选手。只输出一份可提交的 C++ 源码，不要 Markdown，不要解释。
要求：
- 使用 C++11/C++14 兼容写法，避免 C++17/20 特性。
- 代码完整，包含 #include <bits/stdc++.h> 和 main。
- 从 stdin 读入，向 stdout 输出。
- 优先正确性；复杂度满足题目限制。
- 不要输出多余空行和空格，严格按照题目格式
"""


def build_prompt(problem: Problem) -> str:
    samples = []
    for i, s in enumerate(problem.samples, 1):
        samples.append(f"样例 {i} 输入:\n{s.input}\n样例 {i} 输出:\n{s.output}")
    return f"""请解下面的题，输出 C++11/C++14 代码。

题目：{problem.title}
时间限制：{problem.time_limit}
内存限制：{problem.memory_limit}

题面：
{problem.statement}

{chr(10).join(samples)}
"""


class Solver:
    def __init__(self, config: Config):
        if not config.openai_api_key:
            raise RuntimeError("缺少 OPENAI_API_KEY，无法自动生成代码")
        self.client = OpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url)
        self.model = config.openai_model

    def solve(self, problem: Problem) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(problem)},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        code = strip_code_fence(content)
        if "int main" not in code:
            raise RuntimeError("模型输出不像完整 C++ 代码")
        return code