"""
コーパス・メタデータ品質管理ツール
- corpus/ 配下のドキュメントを走査し、品質チェックを実施
- 重複・欠損・古いデータを検出してレポート出力
"""

import os
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
REPORT_OUTPUT = Path(__file__).parent.parent / "logs" / "corpus_quality_report.json"
EXPIRY_DAYS = 180  # 180日以上古いファイルを「古いデータ」と判定


def file_hash(filepath: Path) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def check_corpus_quality(corpus_dir: Path) -> Dict:
    issues = []
    hashes = {}
    now = datetime.now()

    for path in corpus_dir.rglob("*"):
        if not path.is_file():
            continue

        # 欠損・破損チェック
        try:
            size = path.stat().st_size
            if size == 0:
                issues.append({"file": str(path), "type": "empty_file", "detail": "ファイルが空です"})
                continue
        except Exception as e:
            issues.append({"file": str(path), "type": "access_error", "detail": str(e)})
            continue

        # 重複チェック
        h = file_hash(path)
        if h in hashes:
            issues.append({
                "file": str(path),
                "type": "duplicate",
                "detail": f"重複: {hashes[h]} と同一内容"
            })
        else:
            hashes[h] = str(path)

        # 古いデータチェック
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if (now - mtime) > timedelta(days=EXPIRY_DAYS):
            issues.append({
                "file": str(path),
                "type": "outdated",
                "detail": f"最終更新: {mtime.strftime('%Y-%m-%d')} ({EXPIRY_DAYS}日以上更新なし)"
            })

    return {
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(hashes),
        "issues_count": len(issues),
        "issues": issues
    }


def main():
    if not CORPUS_DIR.exists():
        print(f"corpus ディレクトリが見つかりません: {CORPUS_DIR}")
        return

    report = check_corpus_quality(CORPUS_DIR)

    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"チェック完了: {report['total_files']}件, 問題: {report['issues_count']}件")
    print(f"レポート出力: {REPORT_OUTPUT}")
    for issue in report["issues"]:
        print(f"  [{issue['type']}] {issue['file']}: {issue['detail']}")


if __name__ == "__main__":
    main()
