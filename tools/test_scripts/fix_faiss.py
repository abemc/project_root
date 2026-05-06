import json
import faiss
import numpy as np

idx_path = "rag_corpus/corpus.index"
meta_path = "rag_corpus/corpus_meta.json"

index = faiss.read_index(idx_path)
with open(meta_path, "r", encoding="utf-8") as f:
    meta = json.load(f)

ids_to_del = []
for i, item in enumerate(meta):
    if item.get("meta", {}).get("source") == "memory" or item.get("source") == "memory":
        text = item.get("text", "")
        if "iは" in text or "iには" in text or "iの名前" in text or "覚えていません" in text or "私には「オッサン」という名前" in text:
            ids_to_del.append(i)

if ids_to_del:
    index.remove_ids(np.array(ids_to_del, dtype=np.int64))
    new_meta = [m for i, m in enumerate(meta) if i not in ids_to_del]
    faiss.write_index(index, idx_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(new_meta, f, ensure_ascii=False, indent=2)
    print(f"Removed {len(ids_to_del)} bad memories from rag_corpus")
else:
    print("No bad memories found in FAISS")
