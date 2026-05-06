import json
from pathlib import Path
import os

# プロジェクトルートとパス設定
ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "corpus"
META_PATH = CORPUS_DIR / "corpus_meta.json"
DATASET_PATH = CORPUS_DIR / "dataset.jsonl"

def main():
    # 1. 既存のメタデータ(corpus_meta.json)の確認
    if not META_PATH.exists():
        print(f"エラー: {META_PATH} が見つかりません。")
        print("アプリ(app.py)からPDFを追加して、知識ベースを作成してください。")
        return

    print(f"読み込み中: {META_PATH} ...")
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"読み込みエラー: {e}")
        return

    print(f"{len(data)} 件のドキュメントが見つかりました。")
    
    # 2. dataset.jsonl の作成
    print(f"書き込み中: {DATASET_PATH} ...")
    count = 0
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for item in data:
            text = item.get("text", "").strip()
            if not text:
                continue
                
            # ingest.py が期待する形式: {"text": "...", "meta": {...}}
            record = {
                "text": text,
                "meta": item.get("meta", {})
            }
            
            # metaにsourceがない場合、トップレベルからコピーを試みる
            if "source" not in record["meta"]:
                source = item.get("source", "unknown")
                record["meta"]["source"] = source

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            
    print(f"完了: {count} 件のデータを {DATASET_PATH} に出力しました。")
    print("これで 'python src/rag/ingest.py' を実行できます。")

if __name__ == "__main__":
    main()