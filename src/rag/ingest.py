import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import sys

# ============================================================
# RAG用データベース構築スクリプト
# dataset.jsonl を読み込み、ChromaDB (Vector DB) に保存します。
# ============================================================

# パス設定 (src/rag/ingest.py から見たプロジェクトルート)
ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "corpus"
DATASET_PATH = CORPUS_ROOT / "dataset.jsonl"
CHROMA_DB_DIR = CORPUS_ROOT / "chroma_db"
COLLECTION_NAME = "rag_knowledge_base"

# 使用する埋め込みモデル
# 日本語・多言語対応のモデルを指定 (初回実行時に自動ダウンロードされます)
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"

def ingest():
    print(f"Dataset:   {DATASET_PATH}")
    print(f"ChromaDB:  {CHROMA_DB_DIR}")
    
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset not found: {DATASET_PATH}")
        print("Please run 'python -m src.corpus.create_dataset' first.")
        return

    # 1. ChromaDB クライアントの初期化 (永続化設定)
    print("Initializing ChromaDB Client...")
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    # 2. 埋め込み関数の設定 (SentenceTransformersを使用)
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME} ...")
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )

    # 3. コレクションの取得または作成
    #    get_or_create_collection は既存ならロード、なければ作成します
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn
    )

    print("Start indexing documents...")
    
    batch_size = 100
    batch_docs = []
    batch_metas = []
    batch_ids = []
    total_count = 0

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                text = data.get("text", "").strip()
                meta = data.get("meta", {})
                
                # ソース情報などがなければデフォルト値を設定
                if "source" not in meta:
                    meta["source"] = "unknown"
                
                if not text:
                    continue

                # ChromaDBへの登録用リストに追加
                batch_docs.append(text)
                batch_metas.append(meta)
                batch_ids.append(f"doc_{i}")

                # バッチサイズに達したら登録 (upsert: 上書き保存)
                if len(batch_docs) >= batch_size:
                    collection.upsert(
                        documents=batch_docs,
                        metadatas=batch_metas,
                        ids=batch_ids
                    )
                    total_count += len(batch_docs)
                    print(f"Indexed {total_count} documents...", end="\r")
                    
                    batch_docs = []
                    batch_metas = []
                    batch_ids = []

            except json.JSONDecodeError:
                continue

    # 残りのデータを登録
    if batch_docs:
        collection.upsert(
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids
        )
        total_count += len(batch_docs)

    print(f"\nCompleted! Total {total_count} documents stored in '{COLLECTION_NAME}'.")
    print(f"DB Location: {CHROMA_DB_DIR}")

if __name__ == "__main__":
    ingest()