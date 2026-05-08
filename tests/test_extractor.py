import os
import tempfile
import unittest

from analyzer.extractor import extract


class ExtractorTest(unittest.TestCase):
    def test_extract_python(self):
        src = '''"""Module doc"""
import os

class A:
    pass

def fn(x):
    return x
'''
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "m.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(src)
            res = extract(p)
            self.assertIn("functions", res)
            self.assertIn("classes", res)
            self.assertIn("imports", res)
            self.assertEqual(res["classes"], ["A"])
            self.assertIn("fn", res["functions"])


if __name__ == "__main__":
    unittest.main()
