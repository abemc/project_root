import unittest

import sys
import types
import time

from analyzer.llm_client import OpenAIClient


class OpenAITest(unittest.TestCase):
    def test_usage_logged_from_response(self):
        # create fake openai module with ChatCompletion.create
        fake = types.SimpleNamespace()

        class ChatCompletion:
            @staticmethod
            def create(model, messages, max_tokens, temperature):
                return {
                    "choices": [{"message": {"content": "Summary OK"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
                }

        fake.ChatCompletion = ChatCompletion
        fake.error = types.SimpleNamespace(RateLimitError=Exception, APIError=Exception, Timeout=Exception)

        sys.modules["openai"] = fake

        try:
            c = OpenAIClient(api_key="x", model="m.test", max_tokens=10, temperature=0.0)
            out = c.summarize("hello world")
            self.assertEqual(out, "Summary OK")
            hist = c.usage_history
            self.assertTrue(len(hist) >= 1)
            e = hist[-1]
            self.assertEqual(e["total_tokens"], 15)
            self.assertEqual(e["model"], "m.test")
            # timestamp is recent
            self.assertTrue(time.time() - e["timestamp"] < 10)
        finally:
            del sys.modules["openai"]


if __name__ == "__main__":
    unittest.main()
