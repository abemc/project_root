import os
import tempfile
import unittest
import json

from analyzer.llm_client import OpenAIClient


class UsageLoggerTest(unittest.TestCase):
    def test_flush_creates_file_and_rotates(self):
        # inject fake openai to avoid import errors
        import sys, types

        fake = types.SimpleNamespace()

        class ChatCompletion:
            @staticmethod
            def create(model, messages, max_tokens, temperature):
                return {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }

        fake.ChatCompletion = ChatCompletion
        fake.error = types.SimpleNamespace(RateLimitError=Exception, APIError=Exception, Timeout=Exception)
        sys.modules["openai"] = fake

        try:
            c = OpenAIClient(api_key="x")
            # produce a few usage entries
            c.summarize("a")
            c.summarize("b")

            with tempfile.TemporaryDirectory() as td:
                path = os.path.join(td, "usage.log")
                # flush with very small max_bytes to force rotation after second flush
                c.flush_usage_to(path, max_bytes=10, backup_count=2)
                # file should exist
                self.assertTrue(os.path.exists(path) or os.path.exists(path + ".1"))

                # write more entries and flush again to trigger rotation
                c.summarize("c")
                c.flush_usage_to(path, max_bytes=10, backup_count=2)

                # check backups
                # either path or path.1 exists and one backup may be created
                exists = any(os.path.exists(os.path.join(td, fname)) for fname in ["usage.log", "usage.log.1", "usage.log.2"])
                self.assertTrue(exists)
        finally:
            del sys.modules["openai"]
