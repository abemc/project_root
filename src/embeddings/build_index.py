import os
import json
import numpy as np
import faiss
from pathlib import Path
from src.utils.path_utils import get_corpus_path, get_embeddings_path, get_chunks_path, get_meta_dir

CORPUS_PATH = get_corpus_path()
META_DIR = get_meta_dir()
EMBED_DIR = get_embeddings_path()
CHUNK_DIR = get_chunks_path()

INDEX_PATH = CORPUS_PATH / "corpus.index"
META_PATH = CORPUS_PATH / "corpus_meta.json"


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build_index():
    os.makedirs(META_DIR, exist_ok=True)

    all_embeddings = []
    all_meta = []
    global_id = 0

    print("=== Building FAISS index ===")

    for filename in sorted(os.listdir(EMBED_DIR)):
        if not filename.endswith(".npy"):
            continue

        book_id = filename.replace(".npy", "")
        embed_path = os.path.join(EMBED_DIR, filename)
        chunk_path = os.path.join(CHUNK_DIR, f"{book_id}.jsonl")

        print(f"Loading {book_id} ...")

        # --- Load embeddings ---
        emb = np.load(embed_path)
        all_embeddings.append(emb)

        # --- Load metadata ---
        records = load_jsonl(chunk_path)

        for r in records:
            r["global_chunk_id"] = global_id
            all_meta.append(r)
            global_id += 1

    # --- 結合 ---
    embeddings = np.vstack(all_embeddings).astype("float32")
    print(f"Total embeddings: {embeddings.shape}")

    # --- FAISS index ---
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # --- 保存 ---
    faiss.write_index(index, INDEX_PATH)
    print(f"Saved FAISS index to {INDEX_PATH}")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    print(f"Saved metadata to {META_PATH}")


if __name__ == "__main__":
    build_index()