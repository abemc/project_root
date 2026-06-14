#!/usr/bin/env python
"""
失敗ケース収集 CLI ツール

使用例:
  python tools/failure_case_cli.py collect-from-benchmark results/benchmarks/latest.json
  python tools/failure_case_cli.py list --category hallucination --top 10
  python tools/failure_case_cli.py stats
  python tools/failure_case_cli.py export results/failure_cases/ failure_report.csv
"""

import argparse
import json
import sys
import csv
from pathlib import Path
from typing import Optional
from tabulate import tabulate

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.failure_case_collector import (
    FailureCategory,
    FailureCaseCollector,
    collect_failures_from_benchmark,
)


def cmd_collect_from_benchmark(args):
    """ベンチマーク結果から失敗ケースを収集"""
    print(f"📊 Collecting failure cases from: {args.benchmark_file}")

    result = collect_failures_from_benchmark(
        benchmark_result_path=args.benchmark_file,
        storage_dir=args.storage_dir,
    )

    if not result["success"]:
        print(f"❌ Error: {result['error']}")
        return 1

    print(f"\n✅ Collection completed:")
    print(f"   - Detected failures: {result['detected_failures']}")
    print(f"   - Skipped samples: {result['skipped_samples']}")
    print(f"   - Total cases stored: {result['total_cases']}")

    stats = result["statistics"]
    if stats["categories"]:
        print(f"\n📈 Failure categories:")
        for category, count in stats["categories"].items():
            print(f"   - {category}: {count}")

    if stats["top_tags"]:
        print(f"\n🏷️ Top tags:")
        for tag_info in stats["top_tags"]:
            print(f"   - {tag_info['tag']}: {tag_info['count']}")

    return 0


def cmd_list(args):
    """失敗ケース一覧を表示"""
    collector = FailureCaseCollector(storage_dir=args.storage_dir)

    if not collector.cases:
        print("No failure cases found.")
        return 0

    cases = collector.cases

    # フィルタリング
    if args.category:
        cases = [c for c in cases if c.category == args.category]

    if args.severity:
        min_sev, max_sev = args.severity
        cases = [c for c in cases if min_sev <= c.severity <= max_sev]

    # ソート
    if args.sort == "severity":
        cases.sort(key=lambda c: c.severity, reverse=True)
    elif args.sort == "timestamp":
        cases.sort(key=lambda c: c.timestamp, reverse=True)

    # 数制限
    if args.top:
        cases = cases[: args.top]

    # テーブル作成
    table_data = []
    for case in cases:
        severity_indicator = "🔴" if case.severity >= 0.8 else "🟡" if case.severity >= 0.6 else "🟢"
        table_data.append(
            [
                case.case_id,
                case.query[:40] + "..." if len(case.query) > 40 else case.query,
                case.category,
                severity_indicator,
                f"{case.severity:.2f}",
                ", ".join(case.tags) if case.tags else "-",
            ]
        )

    headers = ["Case ID", "Query", "Category", "Severity", "Score", "Tags"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    print(f"\nTotal: {len(cases)} cases")
    return 0


def cmd_stats(args):
    """統計情報を表示"""
    collector = FailureCaseCollector(storage_dir=args.storage_dir)
    stats = collector.get_statistics()

    print("📊 Failure Case Statistics\n")

    print(f"Total Cases: {stats['total_cases']}")

    if stats["categories"]:
        print("\n🏷️ Categories:")
        category_data = [[k, v] for k, v in stats["categories"].items()]
        print(tabulate(category_data, headers=["Category", "Count"], tablefmt="simple"))

    if stats["severity_distribution"]:
        print("\n⚡ Severity Distribution:")
        severity_data = [[k, v] for k, v in stats["severity_distribution"].items()]
        print(tabulate(severity_data, headers=["Level", "Count"], tablefmt="simple"))

    if stats["top_tags"]:
        print("\n🏷️ Top Tags:")
        tag_data = [[t["tag"], t["count"]] for t in stats["top_tags"]]
        print(tabulate(tag_data, headers=["Tag", "Count"], tablefmt="simple"))

    return 0


def cmd_show(args):
    """特定のケースを詳細表示"""
    collector = FailureCaseCollector(storage_dir=args.storage_dir)

    case = None
    for c in collector.cases:
        if c.case_id == args.case_id:
            case = c
            break

    if not case:
        print(f"❌ Case not found: {args.case_id}")
        return 1

    print(f"\n{'='*60}")
    print(f"Case: {case.case_id}")
    print(f"{'='*60}\n")

    print(f"Query:\n  {case.query}\n")
    print(f"Expected Answer:\n  {case.expected_answer}\n")
    print(f"Actual Answer:\n  {case.actual_answer}\n")
    print(f"Category: {case.category}")
    print(f"Severity: {case.severity:.2f}")
    print(f"Confidence Score: {case.confidence_score if case.confidence_score is not None else 'N/A'}")
    print(f"Timestamp: {case.timestamp}\n")

    if case.retrieved_documents:
        print(f"Retrieved Documents: {len(case.retrieved_documents)}")
        for i, doc in enumerate(case.retrieved_documents[:5], 1):
            print(f"  {i}. {doc}")
        if len(case.retrieved_documents) > 5:
            print(f"  ... and {len(case.retrieved_documents) - 5} more")
        print()

    if case.root_cause:
        print(f"Root Cause:\n  {case.root_cause}\n")

    if case.reproduction_steps:
        print(f"Reproduction Steps:\n  {case.reproduction_steps}\n")

    if case.tags:
        print(f"Tags: {', '.join(case.tags)}\n")

    if case.notes:
        print(f"Notes:\n  {case.notes}\n")

    return 0


def cmd_export(args):
    """失敗ケースを CSV に エクスポート"""
    collector = FailureCaseCollector(storage_dir=args.storage_dir)

    if not collector.cases:
        print("No failure cases to export.")
        return 1

    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # ヘッダー
            headers = [
                "case_id",
                "query",
                "expected_answer",
                "actual_answer",
                "category",
                "severity",
                "confidence_score",
                "tags",
                "timestamp",
                "root_cause",
                "notes",
            ]
            writer.writerow(headers)

            # データ行
            for case in collector.cases:
                writer.writerow(
                    [
                        case.case_id,
                        case.query,
                        case.expected_answer,
                        case.actual_answer,
                        case.category,
                        f"{case.severity:.2f}",
                        case.confidence_score if case.confidence_score is not None else "",
                        "; ".join(case.tags) if case.tags else "",
                        case.timestamp,
                        case.root_cause,
                        case.notes,
                    ]
                )

        print(f"✅ Exported {len(collector.cases)} cases to: {output_file}")
        return 0

    except Exception as e:
        print(f"❌ Export failed: {e}")
        return 1


def cmd_clean(args):
    """古いケースを削除"""
    collector = FailureCaseCollector(storage_dir=args.storage_dir)

    original_count = len(collector.cases)

    if args.category:
        collector.cases = [c for c in collector.cases if c.category != args.category]
        removed = original_count - len(collector.cases)
        print(f"Removed {removed} cases with category: {args.category}")

    if args.low_severity is not None:
        collector.cases = [c for c in collector.cases if c.severity >= args.low_severity]
        removed = original_count - len(collector.cases)
        print(f"Removed {removed} cases with severity < {args.low_severity}")

    collector.save()
    print(f"✅ Cleaned. Remaining: {len(collector.cases)} cases")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Failure Case Collector CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect from benchmark results
  python tools/failure_case_cli.py collect-from-benchmark results/benchmarks/latest.json

  # List failure cases
  python tools/failure_case_cli.py list --category hallucination --top 10

  # Show statistics
  python tools/failure_case_cli.py stats

  # Show case details
  python tools/failure_case_cli.py show failure_1234567890_0001

  # Export to CSV
  python tools/failure_case_cli.py export failure_report.csv

  # Clean old cases
  python tools/failure_case_cli.py clean --low-severity 0.5
        """,
    )

    parser.add_argument(
        "--storage-dir",
        default="results/failure_cases",
        help="Storage directory for failure cases (default: results/failure_cases)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # collect-from-benchmark
    parser_collect = subparsers.add_parser(
        "collect-from-benchmark",
        help="Collect failures from benchmark results",
    )
    parser_collect.add_argument("benchmark_file", help="Path to benchmark JSON file")
    parser_collect.set_defaults(func=cmd_collect_from_benchmark)

    # list
    parser_list = subparsers.add_parser("list", help="List failure cases")
    parser_list.add_argument(
        "--category", choices=[c.value for c in FailureCategory], help="Filter by category"
    )
    parser_list.add_argument(
        "--severity",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="Filter by severity range",
    )
    parser_list.add_argument(
        "--sort",
        choices=["severity", "timestamp"],
        default="severity",
        help="Sort by (default: severity)",
    )
    parser_list.add_argument("--top", type=int, help="Limit to top N cases")
    parser_list.set_defaults(func=cmd_list)

    # stats
    parser_stats = subparsers.add_parser("stats", help="Show statistics")
    parser_stats.set_defaults(func=cmd_stats)

    # show
    parser_show = subparsers.add_parser("show", help="Show case details")
    parser_show.add_argument("case_id", help="Case ID")
    parser_show.set_defaults(func=cmd_show)

    # export
    parser_export = subparsers.add_parser("export", help="Export to CSV")
    parser_export.add_argument("output", help="Output CSV file path")
    parser_export.set_defaults(func=cmd_export)

    # clean
    parser_clean = subparsers.add_parser("clean", help="Clean old cases")
    parser_clean.add_argument(
        "--category", help="Remove cases with this category"
    )
    parser_clean.add_argument(
        "--low-severity",
        type=float,
        help="Remove cases with severity below this threshold",
    )
    parser_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
