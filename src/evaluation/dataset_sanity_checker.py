from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatasetSanityChecker:
    """Simple dataset sanity checker for evaluation datasets.

    Usage:
        checker = DatasetSanityChecker(data=[{...}, ...])
        report = checker.run_checks()
    """

    def __init__(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[str] = None,
        required_keys: Optional[List[str]] = None,
        unique_key: str = "query",
    ) -> None:
        raw_data = None
        if file_path:
            p = Path(file_path)
            text = p.read_text(encoding="utf-8")
            raw_data = json.loads(text)
        else:
            raw_data = data

        self.data: List[Dict[str, Any]] = []
        if isinstance(raw_data, dict):
            if "samples" in raw_data and isinstance(raw_data["samples"], list):
                self.data = raw_data["samples"]
            elif "results" in raw_data and isinstance(raw_data["results"], list):
                self.data = raw_data["results"]
            elif "evaluation_data" in raw_data and isinstance(raw_data["evaluation_data"], list):
                self.data = raw_data["evaluation_data"]
            elif "data" in raw_data and isinstance(raw_data["data"], list):
                self.data = raw_data["data"]
            else:
                self.data = [raw_data]
        elif isinstance(raw_data, list):
            self.data = raw_data
        else:
            self.data = []

        default_required = ["query", "expected_answer"]
        if self.data and isinstance(self.data[0], dict):
            first_rec = self.data[0]
            if "ground_truth" in first_rec and "expected_answer" not in first_rec:
                default_required = ["query", "ground_truth"]
            elif "expected_output" in first_rec and "expected_answer" not in first_rec:
                default_required = ["query", "expected_output"]

        self.required_keys = required_keys or default_required
        self.unique_key = unique_key

    def _is_empty(self, val: Any) -> bool:
        return val is None or (isinstance(val, str) and val.strip() == "")

    def check_required_keys(self) -> List[int]:
        missing = []
        for i, rec in enumerate(self.data):
            for k in self.required_keys:
                if k not in rec:
                    missing.append(i)
                    break
        return missing

    def check_empty_values(self) -> List[Dict[str, Any]]:
        empties = []
        for i, rec in enumerate(self.data):
            for k in self.required_keys:
                if k in rec and self._is_empty(rec[k]):
                    empties.append({"index": i, "key": k})
        return empties

    def check_type_mismatches(self, expected_type=str) -> List[Dict[str, Any]]:
        mismatches = []
        for i, rec in enumerate(self.data):
            for k in self.required_keys:
                if k in rec and not isinstance(rec[k], expected_type):
                    mismatches.append({"index": i, "key": k, "type": type(rec[k]).__name__})
        return mismatches

    def check_duplicate_keys(self) -> List[Dict[str, Any]]:
        counts = Counter()
        for rec in self.data:
            key = rec.get(self.unique_key)
            counts[key] += 1
        duplicates = []
        for k, c in counts.items():
            if k is None:
                continue
            if c > 1:
                duplicates.append({"key": k, "count": c})
        return duplicates

    def check_length_ratio(self, field_a: str = "query", field_b: str = "expected_answer", max_ratio: float = 10.0) -> List[Dict[str, Any]]:
        issues = []
        for i, rec in enumerate(self.data):
            a = rec.get(field_a)
            b = rec.get(field_b)
            if not isinstance(a, str) or not isinstance(b, str):
                continue
            la = len(a)
            lb = len(b)
            if lb == 0:
                continue
            ratio = max(la / lb, lb / la) if la and lb else 0
            if ratio > max_ratio:
                issues.append({"index": i, "ratio": ratio, "a_len": la, "b_len": lb})
        return issues

    def run_checks(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {}
        report["total_records"] = len(self.data)
        report["missing_required_keys"] = self.check_required_keys()
        report["empty_values"] = self.check_empty_values()
        report["type_mismatches"] = self.check_type_mismatches()
        report["duplicates"] = self.check_duplicate_keys()
        report["length_ratio_issues"] = self.check_length_ratio()

        # summary counts
        summary = {
            "missing_required_keys": len(report["missing_required_keys"]),
            "empty_values": len(report["empty_values"]),
            "type_mismatches": len(report["type_mismatches"]),
            "duplicates": len(report["duplicates"]),
            "length_ratio_issues": len(report["length_ratio_issues"]),
        }
        report["summary"] = summary
        return report

    def save_report(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.run_checks(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_and_validate(file_path: str) -> Dict[str, Any]:
    """Load dataset from file and run sanity checks, returning a structured report."""
    try:
        checker = DatasetSanityChecker(file_path=file_path)
        report = checker.run_checks()
        errors = []
        if report.get("missing_required_keys"):
            for idx in report["missing_required_keys"]:
                errors.append(f"Record {idx}: Missing required keys (required: {checker.required_keys})")
        if report.get("empty_values"):
            for item in report["empty_values"]:
                errors.append(f"Record {item['index']}: Empty value for key '{item['key']}'")
        if report.get("type_mismatches"):
            for item in report["type_mismatches"]:
                errors.append(f"Record {item['index']}: Type mismatch for key '{item['key']}' (expected str, got {item['type']})")
        if report.get("duplicates"):
            for item in report["duplicates"]:
                errors.append(f"Duplicate key '{item['key']}' found {item['count']} times")
        if report.get("length_ratio_issues"):
            for item in report["length_ratio_issues"]:
                errors.append(f"Record {item['index']}: Length ratio issue (ratio {item['ratio']:.2f}, query length {item['a_len']} vs expected {item['b_len']})")
        
        return {
            "success": True,
            "error": None,
            "report": {
                "total": report["total_records"],
                "summary": report["summary"],
                "errors": errors
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": {}
        }


def validate_samples(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate sample dataset records directly and return structured report."""
    try:
        checker = DatasetSanityChecker(data=data)
        report = checker.run_checks()
        errors = []
        if report.get("missing_required_keys"):
            for idx in report["missing_required_keys"]:
                errors.append(f"Record {idx}: Missing required keys (required: {checker.required_keys})")
        if report.get("empty_values"):
            for item in report["empty_values"]:
                errors.append(f"Record {item['index']}: Empty value for key '{item['key']}'")
        if report.get("type_mismatches"):
            for item in report["type_mismatches"]:
                errors.append(f"Record {item['index']}: Type mismatch for key '{item['key']}' (expected str, got {item['type']})")
        if report.get("duplicates"):
            for item in report["duplicates"]:
                errors.append(f"Duplicate key '{item['key']}' found {item['count']} times")
        if report.get("length_ratio_issues"):
            for item in report["length_ratio_issues"]:
                errors.append(f"Record {item['index']}: Length ratio issue (ratio {item['ratio']:.2f})")
        
        return {
            "success": True,
            "error": None,
            "report": {
                "total": report["total_records"],
                "summary": report["summary"],
                "errors": errors
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": {}
        }


def collect_issues_from_file(file_path: str, out_report: Optional[str] = None) -> Dict[str, Any]:
    """Wrapper matching the interface expected by learning_dashboard.py."""
    res = load_and_validate(file_path)
    if res["success"] and out_report:
        try:
            checker = DatasetSanityChecker(file_path=file_path)
            checker.save_report(out_report)
        except Exception:
            pass
    return res
