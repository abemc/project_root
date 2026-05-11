import json
import torch
# Patch for torchao compatibility (torchao 0.16.0+ requires torch 2.5+, but we have 2.4.1)
if not hasattr(torch, "int1"):
    for i in range(1, 8):
        for dtype in [f"int{i}", f"uint{i}"]:
            setattr(torch, dtype, type(dtype, (), {})())

import numpy as np
from transformers import AutoTokenizer, AutoModel
import faiss
from pathlib import Path
from src.utils.path_utils import get_corpus_path, get_embeddings_path

# --- Path definitions ---
ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = get_corpus_path()
DATASET_PATH = CORPUS_ROOT / "dataset.jsonl"
EMB_DIR = get_embeddings_path()
INDEX_PATH = CORPUS_ROOT / "corpus.index"
META_PATH = CORPUS_ROOT / "corpus_meta.json"
 
# GPUを使用する（自動判定: 利用可能ならcuda、なければcpu）
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# バッチサイズ (GPUメモリ不足の場合は小さくする: 8 -> 2)
BATCH_SIZE = 2

# ============================================================
# bge-m3 をロード（Transformers）
# ============================================================
def load_bge_m3():
    model_name = "BAAI/bge-m3"   # ← 正しいモデル名

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True
    )

    model = AutoModel.from_pretrained(
        model_name,
        trust_remote_code=True,
        use_safetensors=True
    )

    # モデルをデバイスに移す。失敗した場合は CPU にフォールバックする。
    global DEVICE
    try:
        model = model.to(DEVICE)
    except Exception as e:
        print(f"[WARN] Failed to move model to {DEVICE}: {e}. Falling back to CPU.")
        DEVICE = "cpu"
        model = model.to(DEVICE)

    return tokenizer, model


# ============================================================
# チャンク JSON を読み込む
# ============================================================
def load_chunks():
    """
    dataset.jsonl からチャンクデータを読み込む。
    """
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset file not found: {DATASET_PATH}")
        print("Please run 'python -m src.corpus.create_dataset' first.")
        return []
    
    chunks = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks

# ============================================================
# bge-m3 の埋め込み生成（mean pooling）
# -> bge-m3 の推奨に従い、CLSプーリングに変更
# ============================================================
def encode_texts(tokenizer, model, texts, batch_size=BATCH_SIZE):
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        inputs = tokenizer(
            batch,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=8192,
        ).to(DEVICE)

        with torch.no_grad():
            outputs = model(**inputs)
            # CLSプーリング
            emb = outputs.last_hidden_state[:, 0]
            # 正規化
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)

        all_embeddings.append(emb.cpu().numpy())

    return np.vstack(all_embeddings)


# ============================================================
# メイン処理
# ============================================================
def generate_embeddings():
    EMB_DIR.mkdir(exist_ok=True)

    # GPUメモリのキャッシュをクリア
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print("Loading model (bge-m3)...")
    tokenizer, model = load_bge_m3()

    print("Loading chunks...")
    chunks = load_chunks()
    if not chunks:
        print("No chunks to process. Exiting.")
        return
    texts = [c["text"] for c in chunks]

    print(f"Encoding {len(texts)} chunks...")
    embeddings = encode_texts(tokenizer, model, texts, batch_size=BATCH_SIZE)

    # --- FAISS インデックスの作成 ---
    print("Building FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    # INDEX_PATH を明示的に文字列型に変換
    faiss.write_index(index, str(INDEX_PATH))
    print(f"Saved FAISS index to {INDEX_PATH}")

    # --- メタデータの保存 ---
    # 必要に応じてIDを付与
    print("Saving metadata...")
    for i, chunk in enumerate(chunks):
        if "id" not in chunk:
            # 'doc_' + index という形式でIDを振る
            chunk["id"] = f"doc_{i}"
    
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Saved metadata to {META_PATH}")


if __name__ == "__main__":
    generate_embeddings()