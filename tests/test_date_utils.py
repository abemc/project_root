from datetime import date
from src.rag.date_utils import parse_relative_date


def test_parse_yesterday():
    base = date(2026, 5, 17)
    text = "昨日のニュース"
    normalized, iso = parse_relative_date(text, base=base)
    assert iso == "2026-05-16"
    assert "2026-05-16" in normalized


def test_parse_today():
    base = date(2026, 5, 17)
    text = "今日の天気"
    normalized, iso = parse_relative_date(text, base=base)
    assert iso == "2026-05-17"
    assert "2026-05-17" in normalized


def test_no_date():
    base = date(2026, 5, 17)
    text = "誰が本日発売のアルバムを出したか"
    normalized, iso = parse_relative_date(text, base=base)
    assert iso is None
    assert normalized == text
