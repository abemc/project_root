#!/usr/bin/env python
"""
Evaluation Diff CLI

Usage:
  python tools/evaluation_diff_cli.py baseline.json current.json
  python tools/evaluation_diff_cli.py baseline.json current.json --out report.json
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.evaluation.evaluation_diff_viewer import compute_diff_from_files


def main():
    parser = argparse.ArgumentParser(description="Evaluation Diff CLI")
    parser.add_argument("baseline")
    parser.add_argument("current")
    parser.add_argument("--out")
    args = parser.parse_args()

    report = compute_diff_from_files(args.baseline, args.current)
    print(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Saved report to {args.out}")

if __name__ == '__main__':
    main()
