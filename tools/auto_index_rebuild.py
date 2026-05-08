"""
データ追加時の自動インデックス再構築スクリプト
- corpus/ 配下に新規ファイルが追加された際、自動でインデックスを再構築
- ファイル変更検知（watchdog等）と組み合わせて利用可能
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
INDEX_FILE = Path(__file__).parent.parent / "corpus" / "corpus_meta.json"


def compute_hash(filepath: Path) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def build_index(corpus_dir: Path) -> dict:
    """corpus/ 配下の全ファイルをスキャンしてインデックスを構築"""
    index = {}
    for path in corpus_dir.rglob("*"):
        if not path.is_file() or path.name == "corpus_meta.json":
            continue
        try:
            stat = path.stat()
            index[str(path.relative_to(corpus_dir))] = {
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "hash": compute_hash(path)
            }
        except Exception as e:
            index[str(path.relative_to(corpus_dir))] = {"error": str(e)}
    return index


def rebuild_index():
    """インデックスを再構築してcorpus_meta.jsonに保存"""
    print(f"インデックス再構築開始: {CORPUS_DIR}")
    if not CORPUS_DIR.exists():
        print(f"corpus ディレクトリが見つかりません: {CORPUS_DIR}")
        return

    index = build_index(CORPUS_DIR)
    meta = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(index),
        "files": index
    }
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"インデックス再構築完了: {len(index)}件 → {INDEX_FILE}")


if __name__ == "__main__":
    rebuild_index()
