# Auto-Solving-XMUOJ

用于在已授权的 XMUOJ 作业场景中自动读取题目、调用 OpenAI-compatible 模型生成 C++ 解法、运行样例并提交。

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，填写 Cookie 与模型配置。不要提交 `.env`。

## 用法

```bash
python -m src.main fetch
python -m src.main solve
python -m src.main submit
python -m src.main all
```

限制题号：`python -m src.main all --problems A,B`。调试 HTML：`python -m src.main fetch --debug-html`。

输出目录：`data/`、`solutions/`、`submissions/`、`build/`。

## 验证

项目使用 Python 标准库 `unittest`，不需要额外测试依赖：

```bash
python -m unittest discover -s tests
python -m compileall src tests
```

当前已覆盖：

- 题目列表链接解析与去重
- 题面详情中的时限、内存、样例、输入/输出说明解析
- 样例输出标准化逻辑

## 注意事项

- 仅在已授权的作业/比赛场景中使用。
- `.env` 包含 Cookie 和 API Key，必须保持在本地。
- 若 `fetch` 返回 `Please login first`，说明 Cookie 未生效或已过期；重新从浏览器复制完整 `XMUOJ_COOKIE`，或更新 `XMUOJ_SESSION_ID_COOKIE`。
- 提交前会重新运行样例；样例失败时会阻止提交。
