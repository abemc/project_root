import os
import tempfile
import unittest

from analyzer import scan


class ScannerTest(unittest.TestCase):
    def test_scan_basic(self):
        with tempfile.TemporaryDirectory() as td:
            # create sample files
            p1 = os.path.join(td, "a.py")
            with open(p1, "w", encoding="utf-8") as f:
                f.write("# sample python\nprint('hi')\n")

            p2 = os.path.join(td, "README.md")
            with open(p2, "w", encoding="utf-8") as f:
                f.write("# Project\nThis is a README\n")

            res = scan(root=td)
            self.assertIn("project_summary", res)
            self.assertIn("files", res)
            paths = {f["path"] for f in res["files"]}
            self.assertIn("a.py", paths)
            self.assertIn("README.md", paths)

    def test_large_file_handling(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "big.txt")
            # create >1MB file
            with open(p, "w", encoding="utf-8") as f:
                f.write("x" * (1024 * 1024 + 10))
            res = scan(root=td, include_extensions=[".txt"], size_threshold=1024 * 1024)
            self.assertEqual(len(res["files"]), 1)
            meta = res["files"][0]
            self.assertTrue(meta["is_large"])


if __name__ == "__main__":
    unittest.main()
