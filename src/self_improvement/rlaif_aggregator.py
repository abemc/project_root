"""RLAIF aggregation utilities.

Build aggregated AI-feedback metrics from feedback history JSONL.
"""

import json
import os
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_FEEDBACK_HISTORY_PATH = os.path.join(os.getcwd(), "logs", "feedback", "feedback_history.jsonl")
DEFAULT_AI_AGG_PATH = os.path.join(os.getcwd(), "results", "ai_feedback_aggregated.json")


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _extract_ai_fields(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract normalized AI-feedback fields from a feedback record.

    Supported schemas:
    - metadata.ai_feedback.{quality, confidence, csat, nps, adoption_rate, adopted}
    - metadata.{ai_quality, ai_confidence, ai_csat, ai_nps, ai_adoption_rate, ai_adopted}
    - judge-model fallback: model_name starts with "judge" and use top-level rating
    """
    meta = record.get("metadata")
    if not isinstance(meta, dict):
        meta = {}

    ai_block = meta.get("ai_feedback")
    if not isinstance(ai_block, dict):
        ai_block = {}

    quality = _to_float(ai_block.get("quality"))
    if quality is None:
        quality = _to_float(meta.get("ai_quality"))

    confidence = _to_float(ai_block.get("confidence"))
    if confidence is None:
        confidence = _to_float(meta.get("ai_confidence"))

    csat = _to_float(ai_block.get("csat"))
    if csat is None:
        csat = _to_float(meta.get("ai_csat"))

    nps = _to_float(ai_block.get("nps"))
    if nps is None:
        nps = _to_float(meta.get("ai_nps"))

    adoption_rate = _to_float(ai_block.get("adoption_rate"))
    if adoption_rate is None:
        adoption_rate = _to_float(meta.get("ai_adoption_rate"))

    adopted = _to_bool(ai_block.get("adopted"))
    if adopted is None:
        adopted = _to_bool(meta.get("ai_adopted"))

    model_name = record.get("model_name")
    if not isinstance(model_name, str):
        model_name = "unknown"

    # Fallback: if no explicit AI block exists but this appears to be judge output.
    if quality is None and csat is None and model_name.lower().startswith("judge"):
        quality = _to_float(record.get("rating"))

    # Optional conversion: quality(0-1) to csat(1-5)
    if csat is None and quality is not None:
        csat = 1.0 + 4.0 * max(0.0, min(1.0, quality))

    # Ignore entries that do not contain any usable AI signal.
    if all(v is None for v in (quality, confidence, csat, nps, adoption_rate, adopted)):
        return None

    return {
        "quality": quality,
        "confidence": confidence,
        "csat": csat,
        "nps": nps,
        "adoption_rate": adoption_rate,
        "adopted": adopted,
        "judge_model": model_name,
    }


def _safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return float(mean(nums))


def aggregate_ai_feedback(
    feedback_history_path: str = DEFAULT_FEEDBACK_HISTORY_PATH,
    output_path: str = DEFAULT_AI_AGG_PATH,
) -> Dict[str, Any]:
    """Aggregate AI feedback metrics from feedback history and write JSON summary."""
    rows = _load_jsonl(feedback_history_path)
    ai_rows: List[Dict[str, Any]] = []

    for row in rows:
        item = _extract_ai_fields(row)
        if item is not None:
            ai_rows.append(item)

    by_judge_model: Dict[str, int] = {}
    for item in ai_rows:
        key = item.get("judge_model") or "unknown"
        by_judge_model[key] = by_judge_model.get(key, 0) + 1

    explicit_adoption = [v for v in (r.get("adoption_rate") for r in ai_rows) if isinstance(v, (int, float))]
    adopted_flags = [r.get("adopted") for r in ai_rows if isinstance(r.get("adopted"), bool)]

    if explicit_adoption:
        adoption_rate = _safe_mean(explicit_adoption)
    elif adopted_flags:
        adoption_rate = float(sum(1 for x in adopted_flags if x) / len(adopted_flags))
    else:
        adoption_rate = None

    summary: Dict[str, Any] = {
        "total_entries": len(ai_rows),
        "quality_mean": _safe_mean(r.get("quality") for r in ai_rows),
        "confidence_mean": _safe_mean(r.get("confidence") for r in ai_rows),
        "csat_mean": _safe_mean(r.get("csat") for r in ai_rows),
        "nps_mean": _safe_mean(r.get("nps") for r in ai_rows),
        "adoption_rate": adoption_rate,
        "by_judge_model": by_judge_model,
        "source": "feedback_history_auto_aggregate",
    }

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary
