import os
import json
import numpy as np\nfrom typing import List, Dict
from pathlib import Path

# Patch for torchao compatibility (torchao 0.16.0+ requires torch 2.5+, but we have 2.4.1)
import torch
if not hasattr(torch, "int1"):
    for i in range(1, 8):
        for dtype in [f\"int{i}\", f\"uint{i}\"]:
            setattr(torch, dtype, type(dtype, (), {})())

from sentence_transformers import SentenceTransformer
from src.corpus.chunk_text import chunk_text
from src.utils.path_utils import get_normalized_path, get_chunks_path, get_embeddings_path
import tiktoken

# ============================================================
# モデル設定（bge-m3）
# ============================================================
EMBED_MODEL = "BAAI/bge-m3"
model = SentenceTransformer(EMBED_MODEL, device="cuda")

enc = tiktoken.get_encoding("cl100k_base")


# ============================================================
# Utility
# ============================================================
def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_jsonl(records: List[Dict], out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ============================================================
# 1冊分の処理
# ============================================================
def process_book(book_id: str):
    norm_dir = get_normalized_path()
    chunks_dir = get_chunks_path()
    embed_dir = get_embeddings_path()
    
    norm_path = norm_dir / f\"{book_id}.txt\"
    chunk_path = chunks_dir / f\"{book_id}.jsonl\"
    embed_path = embed_dir / f\"{book_id}.npy\"

    print(f"\n=== Processing {book_id} ===")

    # --- Load text ---
    text = load_text(norm_path)

    # --- Chunking ---
    chunks = chunk_text(text)
    print(f"Chunks created: {len(chunks)}")

    # --- メタデータ作成 ---
    records = []
    for i, c in enumerate(chunks):
        records.append({
            "book_id": book_id,
            "chunk_id": i,
            "text": c,
            "tokens": count_tokens(c)
        })

    # --- Save chunks (jsonl) ---
    save_jsonl(records, chunk_path)
    print(f"Saved chunks to {chunk_path}")

    # --- Embedding ---
    texts = [r["text"] for r in records]
    embeddings = model.encode(texts, batch_size=2, normalize_embeddings=True)
    np.save(embed_path, embeddings)
    print(f"Saved embeddings to {embed_path}")


# ============================================================
# 全冊処理
# ============================================================
def process_all_books():
    norm_dir = get_normalized_path()
    for filename in sorted(os.listdir(norm_dir)):
        if filename.endswith(".txt"):
            book_id = filename.replace(".txt", "")
            process_book(book_id)


if __name__ == "__main__":
    process_all_books()