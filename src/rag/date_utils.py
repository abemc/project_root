from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

try:
    import dateparser
    _HAS_DATEPARSER = True
except Exception:
    dateparser = None
    _HAS_DATEPARSER = False


def _fallback_jp_parse(text: str, base: Optional[date] = None) -> Optional[date]:
    """Very small fallback parser for common Japanese relative tokens.
    Returns a date object or None.
    """
    if base is None:
        base = datetime.now().date()
    t = text
    if "一昨日" in t:
        return base - timedelta(days=2)
    if "昨日" in t:
        return base - timedelta(days=1)
    if "今日" in t:
        return base
    if "明日" in t:
        return base + timedelta(days=1)
    # simple weekday handling like '先週火曜日' is not supported in fallback
    return None


def parse_relative_date(text: str, base: Optional[date] = None) -> Tuple[str, Optional[str]]:
    """Parse relative dates from `text` and return a tuple of (normalized_text, iso_date_or_None).

    If a date is detected, the returned `normalized_text` will have the matched
    relative word replaced with an ISO date (YYYY-MM-DD). Otherwise the original
    text is returned with None for the date.
    """
    if base is None:
        base = datetime.now().date()

    # Use dateparser when available for robust parsing
    if _HAS_DATEPARSER:
        try:
            settings = {"PREFER_DATES_FROM": "past", "RELATIVE_BASE": datetime.combine(base, datetime.min.time()), "LANGUAGE": "ja"}
            dp = dateparser.parse(text, settings=settings, languages=["ja"])  # type: ignore[arg-type]
            if dp is not None:
                iso = dp.date().isoformat()
                # Replace common Japanese tokens if present to avoid duplication
                for tok in ["一昨日", "昨日", "今日", "明日"]:
                    if tok in text:
                        return (text.replace(tok, iso), iso)
                # If no token matched, just append the date
                return (f"{text} {iso}", iso)
        except Exception:
            pass

    # Fallback heuristics
    try:
        parsed = _fallback_jp_parse(text, base=base)
        if parsed:
            iso = parsed.isoformat()
            for tok in ["一昨日", "昨日", "今日", "明日"]:
                if tok in text:
                    return (text.replace(tok, iso), iso)
            return (f"{text} {iso}", iso)
    except Exception:
        pass

    return (text, None)


__all__ = ["parse_relative_date"]
