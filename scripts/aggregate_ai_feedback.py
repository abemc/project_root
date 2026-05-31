#!/usr/bin/env python3
"""Aggregate AI feedback JSONL into summary JSON for RLAIF."""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.self_improvement.rlaif_aggregator import (
    DEFAULT_AI_AGG_PATH,
    DEFAULT_FEEDBACK_HISTORY_PATH,
    aggregate_ai_feedback,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate AI feedback metrics")
    parser.add_argument("--input", dest="input_path", default=DEFAULT_FEEDBACK_HISTORY_PATH)
    parser.add_argument("--output", dest="output_path", default=DEFAULT_AI_AGG_PATH)
    args = parser.parse_args()

    summary = aggregate_ai_feedback(args.input_path, args.output_path)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Wrote: {os.path.abspath(args.output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
