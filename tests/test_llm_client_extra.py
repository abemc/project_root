import re
from analyzer.llm_client import MockLLMClient


def test_date_responses_languages():
    c = MockLLMClient()
    assert "2026" in c.summarize("What is today's date?") or "date" in c.summarize("What is today's date?")
    assert "fecha" in c.summarize("¿Qué fecha es hoy?") or "fecha" in c.summarize("¿Qué fecha es hoy?")
    assert ("Nous" in c.summarize("Quelle est la date aujourd'hui?")) or ("2026" in c.summarize("Quelle est la date aujourd'hui?"))


def test_rfc3339_format():
    c = MockLLMClient()
    out = c.summarize("What's the date RFC3339")
    # RFC3339 roughly: YYYY-MM-DDThh:mm:ss+hh:mm
    m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:?\d{0,2}[+\-]\d{2}:\d{2}", out)
    assert m is not None, f"expected RFC3339-like output, got: {out}"


def test_time_in_tokyo():
    c = MockLLMClient()
    out = c.summarize("What time is it in Tokyo?")
    assert any(x in out.lower() for x in ["current time", "現在の時刻", "il est", "la hora"]) or re.search(r"\d{2}:\d{2}", out)
