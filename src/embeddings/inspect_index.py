import faiss
import json

# ============================================================
# 設定
# ============================================================
from src.utils.path_utils import get_corpus_path

CORPUS_ROOT = get_corpus_path()
INDEX_PATH = CORPUS_ROOT / "corpus.index"
META_PATH = CORPUS_ROOT / "corpus_meta.json"

def main():
    """
    生成された知識ベース（インデックスとメタデータ）の内容を検証するツール。
    """
    print("=== Inspecting Knowledge Base ===")
    print(f"Root Directory: {CORPUS_ROOT.resolve()}")
    print(f"Index File:     {INDEX_PATH}")
    print(f"Metadata File:  {META_PATH}\n")

    index = None
    meta = []

    # 1. FAISSインデックスの確認
    if INDEX_PATH.exists():
        try:
            print("--- Loading FAISS Index ---")
            index = faiss.read_index(str(INDEX_PATH))
            print(f"Vectors (ntotal): {index.ntotal}")
            print(f"Dimension (d):    {index.d}")
            print(f"Is Trained:       {index.is_trained}")
            print(f"Metric Type:      {index.metric_type} (1=L2, 2=IP)")
        except Exception as e:
            print(f"[ERROR] Failed to load index: {e}")
    else:
        print(f"[ERROR] Index file not found at {INDEX_PATH}")

    print("-" * 30)

    # 2. メタデータの確認
    if META_PATH.exists():
        try:
            print("--- Loading Metadata ---")
            with open(META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            print(f"Metadata Entries: {len(meta)}")
            
            if len(meta) > 0:
                print("\n[Sample Record (First)]")
                print(json.dumps(meta[0], indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[ERROR] Failed to load metadata: {e}")
    else:
        print(f"[ERROR] Metadata file not found at {META_PATH}")

    print("-" * 30)

    # 3. 整合性チェック
    if index is not None:
        if index.ntotal == len(meta):
            print("✅ Status: OK (Vector count matches metadata count)")
        else:
            print(f"⚠️ Status: MISMATCH (Vectors: {index.ntotal} != Metadata: {len(meta)})")
            print("   インデックスとメタデータの同期が取れていない可能性があります。")

if __name__ == "__main__":
    main()