import unittest

from analyzer.llm_client import MockLLMClient


class LLMClientTest(unittest.TestCase):
    def test_mock_summary(self):
        c = MockLLMClient()
        s = c.summarize("hello world")
        self.assertIn("MOCK_SUMMARY", s)

    def test_batch(self):
        c = MockLLMClient()
        out = c.batch_summarize(["a" * 10, "b" * 20])
        self.assertIn("length=10", out)
        self.assertIn("length=20", out)


if __name__ == "__main__":
    unittest.main()
