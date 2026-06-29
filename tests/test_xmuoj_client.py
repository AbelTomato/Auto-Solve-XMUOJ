import unittest

from src.config import Config
from src.xmuoj_client import XMUOJClient


def make_config() -> Config:
    return Config(
        base_url="https://xmuoj.com",
        contest_url="https://xmuoj.com/contest/359/problems",
        cookie="csrftoken=abc; sessionid=def",
        verify_ssl=True,
        openai_api_key="key",
        openai_base_url="https://api.example.com/v1",
        openai_model="model",
        auto_submit=False,
        default_language="cpp",
        problem_filter=[],
        max_submissions_per_run=20,
    )


class XMUOJClientTest(unittest.TestCase):
    def test_sets_csrf_header_from_cookie(self):
        client = XMUOJClient(make_config())

        self.assertEqual(client.session.headers["X-CSRFToken"], "abc")

    def test_api_language_maps_cpp_to_c_plus_plus(self):
        client = XMUOJClient(make_config())

        self.assertEqual(client.api_language_value(), "C++")

    def test_api_submit_response_error_is_not_success(self):
        client = XMUOJClient(make_config())
        client.post_json = lambda path, payload: {"error": "invalid-problem_id", "data": "problem_id: A valid integer is required."}

        with self.assertRaisesRegex(RuntimeError, "invalid-problem_id"):
            client.submit_code_api("JD001", "int main(){}")


if __name__ == "__main__":
    unittest.main()