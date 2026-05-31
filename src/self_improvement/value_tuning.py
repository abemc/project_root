from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
import re


VALUE_PATTERNS = {
    "accuracy": [r"正確", r"誤り", r"事実", r"正しい", r"根拠不足"],
    "clarity": [r"わかりやす", r"明確", r"読みやす", r"曖昧", r"複雑すぎ"],
    "helpfulness": [r"有用", r"役立", r"助か", r"実用", r"使える"],
    "safety": [r"安全", r"危険", r"リスク", r"配慮", r"倫理"],
    "transparency": [r"出典", r"根拠", r"透明", r"理由", r"説明不足"],
    "neutrality": [r"中立", r"偏り", r"公平", r"バランス"],
}

POSITIVE_HINTS = [r"良い", r"十分", r"適切", r"明確", r"役立", r"安全", r"正確", r"丁寧"]
NEGATIVE_HINTS = [r"悪い", r"不足", r"不正確", r"危険", r"曖昧", r"偏り", r"改善", r"複雑"]


def _normalize_signal(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def infer_value_signals(
    tags: Optional[List[str]] = None,
    feedback_text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Infer lightweight value-alignment signals from feedback text/tags.

    Returns a sparse dict of value dimension -> score in [0, 1].
    Only dimensions with evidence are returned.
    """
    text_parts: List[str] = []
    if tags:
        text_parts.extend([str(t) for t in tags if t])
    if feedback_text:
        text_parts.append(str(feedback_text))
    if isinstance(metadata, dict):
        value_notes = metadata.get("value_notes")
        if value_notes:
            text_parts.append(str(value_notes))

    corpus = " ".join(text_parts).strip()
    if not corpus:
        return {}

    is_positive = any(re.search(p, corpus, re.IGNORECASE) for p in POSITIVE_HINTS)
    is_negative = any(re.search(p, corpus, re.IGNORECASE) for p in NEGATIVE_HINTS)
    base = 0.75 if is_positive and not is_negative else 0.25 if is_negative and not is_positive else 0.5

    signals: Dict[str, float] = {}
    for key, patterns in VALUE_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, corpus, re.IGNORECASE))
        if matches <= 0:
            continue
        boost = min(0.2, 0.05 * (matches - 1))
        signals[key] = _normalize_signal(base + boost)

    return signals


def aggregate_value_signals(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate value signals from training-feedback-like records."""
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    total_items = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        total_items += 1
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        signals = metadata.get("value_signals") if isinstance(metadata.get("value_signals"), dict) else {}
        if not signals:
            signals = infer_value_signals(
                tags=item.get("tags") if isinstance(item.get("tags"), list) else [],
                feedback_text=item.get("feedback") or item.get("feedback_text"),
                metadata=metadata,
            )
        for key, value in signals.items():
            try:
                fval = float(value)
            except Exception:
                continue
            totals[key] = totals.get(key, 0.0) + fval
            counts[key] = counts.get(key, 0) + 1

    means = {
        key: _normalize_signal(totals[key] / counts[key])
        for key in sorted(totals.keys())
        if counts.get(key)
    }
    return {
        "total_items": total_items,
        "signal_counts": counts,
        "signal_means": means,
    }
