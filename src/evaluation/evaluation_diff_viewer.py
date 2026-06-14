from typing import List, Dict, Any
from pathlib import Path
import json


def _get_score(sample: Dict[str, Any]) -> float:
    # Prefer an explicit numeric score
    if isinstance(sample.get("score"), (int, float)):
        return float(sample.get("score"))
    # Fallback: binary correctness from predicted/expected
    if "predicted" in sample and "expected" in sample:
        return 1.0 if sample.get("predicted") == sample.get("expected") else 0.0
    # Unknown -> NaN-ish (use 0.0)
    return 0.0


def compute_diff(baseline: List[Dict[str, Any]], current: List[Dict[str, Any]], id_key: str = "id") -> Dict[str, Any]:
    """Compute diff between baseline and current evaluation samples.

    Each sample is a dict containing at least an `id`. Optionally `score` numeric or `predicted`/`expected`.

    Returns a report dict with keys: summary, items (per-case diff), top_regressions
    """
    base_map = {s[id_key]: s for s in baseline}
    cur_map = {s[id_key]: s for s in current}

    all_ids = set(base_map) | set(cur_map)
    items = []
    summary = {"total_baseline": len(baseline), "total_current": len(current), "added": 0, "removed": 0, "improved": 0, "regressed": 0, "unchanged": 0}

    for _id in sorted(all_ids):
        b = base_map.get(_id)
        c = cur_map.get(_id)
        if b and not c:
            summary["removed"] += 1
            items.append({"id": _id, "type": "removed", "baseline": b, "current": None})
            continue
        if c and not b:
            summary["added"] += 1
            items.append({"id": _id, "type": "added", "baseline": None, "current": c})
            continue
        # present in both
        b_score = _get_score(b)
        c_score = _get_score(c)
        delta = c_score - b_score
        detail = {"id": _id, "baseline_score": b_score, "current_score": c_score, "delta": delta, "baseline": b, "current": c}
        # threshold for change
        eps = 1e-3
        if delta > eps:
            summary["improved"] += 1
            detail['type'] = 'improved'
        elif delta < -eps:
            summary["regressed"] += 1
            detail['type'] = 'regressed'
        else:
            summary["unchanged"] += 1
            detail['type'] = 'unchanged'
        items.append(detail)

    # top regressions (most negative delta)
    regressions = [it for it in items if it.get("type") == "regressed"]
    regressions_sorted = sorted(regressions, key=lambda x: x.get("delta", 0))[:50]

    report = {
        "summary": summary,
        "items": items,
        "top_regressions": regressions_sorted,
    }
    return report


def load_samples_from_file(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # expect list or dict with 'samples'
    if isinstance(data, dict) and "samples" in data:
        return data["samples"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported dataset format: expected list or {samples: [...]}")


def compute_diff_from_files(baseline_path: str, current_path: str, id_key: str = "id") -> Dict[str, Any]:
    b = load_samples_from_file(baseline_path)
    c = load_samples_from_file(current_path)
    return compute_diff(b, c, id_key=id_key)


def _flatten_item_to_row(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "baseline_score": item.get("baseline_score"),
        "current_score": item.get("current_score"),
        "delta": item.get("delta"),
    }


def report_to_csv_bytes(report: Dict[str, Any]) -> bytes:
    """Convert a diff report to CSV bytes for download/export."""
    import io, csv

    items = report.get("items", [])
    rows = [_flatten_item_to_row(it) for it in items]
    output = io.StringIO()
    fieldnames = ["id", "type", "baseline_score", "current_score", "delta"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: (r.get(k) if r.get(k) is not None else "") for k in fieldnames})
    return output.getvalue().encode("utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluation Diff Viewer CLI")
    parser.add_argument("baseline", help="Baseline evaluation JSON file")
    parser.add_argument("current", help="Current evaluation JSON file")
    parser.add_argument("--id-key", default="id", help="Key to use as unique id")
    parser.add_argument("--out", help="Write JSON report to file")
    args = parser.parse_args()
    report = compute_diff_from_files(args.baseline, args.current, id_key=args.id_key)
    print(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Saved full report to: {args.out}")
