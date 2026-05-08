import os
import tempfile
import unittest

from analyzer import scanner
from analyzer.llm_client import MockLLMClient
from analyzer.summarizer import summarize_files


class SummarizerTest(unittest.TestCase):
    def test_summarize_map_reduce(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "a.txt")
            with open(p1, "w", encoding="utf-8") as f:
                f.write("hello world\n" * 100)

            res = scanner.scan(root=td, include_extensions=[".txt"]) 
            client = MockLLMClient()
            summ = summarize_files(res.get("files", []), td, client, chunk_size=50)
            self.assertIn("MOCK_SUMMARY", summ)


if __name__ == "__main__":
    unittest.main()
