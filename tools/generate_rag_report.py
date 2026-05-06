"""
検索精度評価レポート自動生成スクリプト
- eval_rag_accuracy.py の評価結果をもとに、Markdown形式のレポートを自動生成
- logs/rag_accuracy_report_YYYYMMDD.md として出力
"""

import json
from datetime import datetime
from pathlib import Path

QUERIES_FILE = Path(__file__).parent / "queries.json"
REPORT_DIR = Path(__file__).parent.parent / "logs"


def query_rag_system(query: str) -> dict:
    # 仮実装: 実際はRAG APIやローカル関数に置き換えてください
    return {"answer": "ダミー回答", "evidence": ["doc1"]}


def evaluate_rag(queries: list) -> dict:
    results = []
    for q in queries:
        res = query_rag_system(q["query"])
        correct = q["expected_answer"] in res["answer"]
        results.append({
            "query": q["query"],
            "expected": q["expected_answer"],
            "actual": res["answer"],
            "evidence": res["evidence"],
            "correct": correct
        })
    accuracy = sum(r["correct"] for r in results) / len(results) if results else 0.0
    return {"results": results, "accuracy": accuracy}


def generate_report(report: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# RAG検索精度評価レポート",
        f"",
        f"**生成日時**: {now}",
        f"",
        f"## サマリー",
        f"",
        f"| 項目 | 値 |",
        f"|------|-----|",
        f"| 評価クエリ数 | {len(report['results'])} |",
        f"| 正解率 | {report['accuracy']*100:.1f}% |",
        f"",
        f"## 詳細結果",
        f"",
        f"| クエリ | 期待回答 | 実際の回答 | 正解 | 根拠文書 |",
        f"|--------|----------|-----------|------|---------|",
    ]
    for r in report["results"]:
        correct_mark = "✅" if r["correct"] else "❌"
        evidence = ", ".join(r["evidence"])
        lines.append(f"| {r['query']} | {r['expected']} | {r['actual']} | {correct_mark} | {evidence} |")
    lines += [
        f"",
        f"---",
        f"",
        f"> このレポートは自動生成されています。問題があれば担当者に連絡してください。"
    ]
    return "\n".join(lines)


def main():
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)

    report = evaluate_rag(queries)
    md = generate_report(report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = REPORT_DIR / f"rag_accuracy_report_{date_str}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"レポート生成完了: {out_path}")
    print(f"正解率: {report['accuracy']*100:.1f}%")


if __name__ == "__main__":
    main()
