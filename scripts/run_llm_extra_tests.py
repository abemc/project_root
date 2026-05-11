import re
import sys
from pathlib import Path

# ensure project root on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analyzer.llm_client import MockLLMClient


def fail(msg: str):
    print('FAIL:', msg)
    sys.exit(1)


def main():
    c = MockLLMClient()

    # date English
    out_en = c.summarize("What is today's date?")
    if not ("202" in out_en or "date" in out_en or "今日" in out_en):
        fail(f"unexpected english date response: {out_en}")

    # spanish
    out_es = c.summarize("¿Qué fecha es hoy?")
    if not ("fecha" in out_es or "202" in out_es):
        fail(f"unexpected spanish date response: {out_es}")

    # french
    out_fr = c.summarize("Quelle est la date aujourd'hui?")
    if not ("Nous" in out_fr or "202" in out_fr or "date" in out_fr):
        fail(f"unexpected french date response: {out_fr}")

    # rfc3339
    out_rfc = c.summarize("Give me the date in RFC3339 format")
    m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+\-]\d{2}:\d{2}", out_rfc)
    if not m:
        fail(f"expected RFC3339-like output, got: {out_rfc}")

    # time in tokyo
    out_tz = c.summarize("What time is it in Tokyo?")
    if not re.search(r"\d{2}:\d{2}", out_tz):
        fail(f"unexpected time response: {out_tz}")

    print('All checks passed')


if __name__ == '__main__':
    main()
