import unittest

from src.models import Problem
from src.parser import parse_problem_detail, parse_problem_detail_api, parse_problem_list, parse_problem_list_api, problem_to_markdown


class ParserTest(unittest.TestCase):
    def test_parse_problem_list_deduplicates_problem_links(self):
        html = """
        <a href="/problem/1001">A + B Problem</a>
        <a href="/problem/1001">A + B Problem</a>
        <a href="/contest/359/problem/1002">Second</a>
        """

        problems = parse_problem_list(html, "https://xmuoj.com")

        self.assertEqual([p.index for p in problems], ["A", "B"])
        self.assertEqual(problems[0].url, "https://xmuoj.com/problem/1001")
        self.assertEqual(problems[0].problem_id, "1001")

    def test_parse_problem_list_api_extracts_spa_api_payload(self):
        data = {"data": {"results": [{"_id": "abc", "display_id": "A", "title": "API Problem"}]}}

        problems = parse_problem_list_api(data, "https://xmuoj.com", "359")

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].index, "A")
        self.assertEqual(problems[0].problem_id, "abc")
        self.assertEqual(problems[0].url, "https://xmuoj.com/contest/359/problem/A")

    def test_parse_problem_list_api_assigns_indices_from_top_level_order(self):
        data = {"data": [{"_id": "JD001", "id": 7105, "title": "铁令求和"}, {"_id": "JD002", "id": 7106, "title": "铁令相乘"}]}

        problems = parse_problem_list_api(data, "https://xmuoj.com", "359")

        self.assertEqual([p.index for p in problems], ["A", "B"])
        self.assertEqual([p.problem_id for p in problems], ["7105", "7106"])

    def test_parse_problem_list_api_uses_excel_style_indices_after_z(self):
        data = {"data": [{"_id": f"JD{i:03d}", "title": f"Problem {i}"} for i in range(1, 29)]}

        problems = parse_problem_list_api(data, "https://xmuoj.com", "359")

        self.assertEqual(problems[25].index, "Z")
        self.assertEqual(problems[26].index, "AA")
        self.assertEqual(problems[27].index, "AB")

    def test_parse_problem_list_api_reports_login_required(self):
        with self.assertRaisesRegex(RuntimeError, "Cookie"):
            parse_problem_list_api({"error": "error", "data": "Please login first."}, "https://xmuoj.com", "359")

    def test_parse_problem_detail_extracts_limits_samples_and_io_sections(self):
        problem = Problem(index="A", title="Old", url="https://xmuoj.com/problem/1001")
        html = """
        <h1>New Title</h1>
        <p>Time Limit: 1s</p>
        <p>Memory Limit: 128 MB</p>
        <h2>Description</h2>
        <p>Calculate a+b.</p>
        <h2>Input</h2>
        <p>Two integers.</p>
        <h2>Output</h2>
        <p>Their sum.</p>
        <h2>Sample Input</h2>
        <pre>1 2</pre>
        <h2>Sample Output</h2>
        <pre>3</pre>
        """

        parsed = parse_problem_detail(problem, html)

        self.assertEqual(parsed.title, "New Title")
        self.assertEqual(parsed.time_limit, "1s")
        self.assertEqual(parsed.memory_limit, "128 MB")
        self.assertEqual(parsed.input_description, "Two integers.")
        self.assertEqual(parsed.output_description, "Their sum.")
        self.assertEqual(len(parsed.samples), 1)
        self.assertEqual(parsed.samples[0].input, "1 2")
        self.assertEqual(parsed.samples[0].output, "3")

        markdown = problem_to_markdown(parsed)
        self.assertIn("## 输入", markdown)
        self.assertIn("## 输出", markdown)

    def test_parse_problem_detail_api_extracts_samples(self):
        problem = Problem(index="A", title="Old", url="https://xmuoj.com/contest/359/problem/A", problem_id="abc")
        data = {
            "data": {
                "title": "API Title",
                "description": "Do it.",
                "input_description": "Input text.",
                "output_description": "Output text.",
                "samples": [{"input": "1 2", "output": "3"}],
            }
        }

        parsed = parse_problem_detail_api(problem, data)

        self.assertEqual(parsed.title, "API Title")
        self.assertEqual(parsed.input_description, "Input text.")
        self.assertEqual(parsed.samples[0].output, "3")

    def test_parse_problem_detail_api_converts_html_to_text(self):
        problem = Problem(index="A", title="Old", url="https://xmuoj.com/contest/359/problem/A", problem_id="7105")
        data = {"data": {"title": "API Title", "description": "<p>Hello</p>", "input_description": "<p>Input text.</p>", "output_description": "<p>Output text.</p>"}}

        parsed = parse_problem_detail_api(problem, data)

        self.assertEqual(parsed.statement, "Hello\n\nInput text.\n\nOutput text.")


if __name__ == "__main__":
    unittest.main()
