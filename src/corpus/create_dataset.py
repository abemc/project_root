import json
from pathlib import Path
# 同じパッケージ内の chunk_text モジュールを利用
from .chunk_text import chunk_text

# ============================================================
# STEP 0: パス設定
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "corpus"
NORMALIZED_DIR = CORPUS_ROOT / "normalized"  # 入力: 正規化済みテキスト
OUTPUT_JSONL = CORPUS_ROOT / "dataset.jsonl" # 出力: JSONLデータセット


# ============================================================
# STEP 1: データセット作成メイン処理
# ============================================================
def create_dataset():
    """
    正規化済みテキストを読み込み、チャンク化してJSONL形式で保存する。
    出力形式: {"text": "...", "meta": {"source": "..."}}
    """
    print(f"Input Directory: {NORMALIZED_DIR}")
    print(f"Output File:     {OUTPUT_JSONL}")

    # 1. 入力ディレクトリの確認
    if not NORMALIZED_DIR.exists():
        print(f"[ERROR] Directory not found: {NORMALIZED_DIR}")
        print("先に normalize_all.py を実行してテキストを正規化してください。")
        return

    # 2. テキストファイルの取得
    files = sorted(list(NORMALIZED_DIR.glob("*.txt")))
    if not files:
        print(f"[WARN] No text files found in {NORMALIZED_DIR}")
        return

    print(f"Found {len(files)} files. Processing...")

    total_chunks = 0
    
    # 3. ファイルごとの処理
    #    追記ではなく上書きモード("w")でファイルを作成
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as out_f:
        for i, file_path in enumerate(files, 1):
            book_id = file_path.stem  # 拡張子なしのファイル名 (例: book_001)
            print(f"[{i}/{len(files)}] Processing {book_id} ...")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                print(f"  [ERROR] Failed to read {file_path}: {e}")
                continue

            # 4. チャンク化 (chunk_text.py の機能を利用)
            #    セクション分割 -> 文分割 -> トークン数制限で結合
            chunks = chunk_text(text)

            # 5. JSONL に書き込み
            for chunk in chunks:
                record = {
                    "text": chunk,
                    "meta": {"source": book_id}
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1
            
            print(f"  -> {len(chunks)} chunks")

    print(f"\nCompleted. Total {total_chunks} chunks saved to {OUTPUT_JSONL.name}")


if __name__ == "__main__":
    create_dataset()