import unittest

from src.runner import normalize_output


class RunnerTest(unittest.TestCase):
    def test_normalize_output_ignores_trailing_spaces_and_blank_edges(self):
        self.assertEqual(normalize_output("\n1 2   \r\n3\n\n"), "1 2\n3")

    def test_normalize_output_preserves_meaningful_inner_blank_lines(self):
        self.assertEqual(normalize_output("a\n\n b "), "a\n\n b")


if __name__ == "__main__":
    unittest.main()
