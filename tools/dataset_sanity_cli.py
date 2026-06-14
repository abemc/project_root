#!/usr/bin/env python
"""
Dataset Sanity Checker CLI

Usage:
  python tools/dataset_sanity_cli.py check path/to/dataset.json
  python tools/dataset_sanity_cli.py check --file results/benchmarks/latest.json
  python tools/dataset_sanity_cli.py save-report path/to/dataset.json out.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.dataset_sanity_checker import load_and_validate, validate_samples, DatasetSanityChecker


def cmd_check(args):
    path = args.file
    out = load_and_validate(path)
    if not out.get("success"):
        print("Error:", out.get("error"))
        return 2
    report = out.get("report")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_save_report(args):
    path = args.file
    out_path = args.out
    checker = DatasetSanityChecker(file_path=path)
    checker.save_report(out_path)
    print(f"Saved report to: {out_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Dataset Sanity CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_check = sub.add_parser("check")
    p_check.add_argument("file", help="Path to dataset json")
    p_check.set_defaults(func=cmd_check)

    p_save = sub.add_parser("save-report")
    p_save.add_argument("file", help="Path to dataset json")
    p_save.add_argument("out", help="Output path for report json")
    p_save.set_defaults(func=cmd_save_report)

    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
