import os
import tempfile
import unittest

from analyzer.cli import run_analyze
from analyzer.llm_client import MockLLMClient


class CLITest(unittest.TestCase):
    def test_run_analyze_returns(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write("print(1)\n")
            res = run_analyze(root=td, out=None, llm_client=MockLLMClient())
            self.assertIn("project_summary", res)
            self.assertIn("analysis_summary", res)


if __name__ == "__main__":
    unittest.main()
