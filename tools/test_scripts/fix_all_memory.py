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
        ids_to_del.append(i)

if ids_to_del:
    index.remove_ids(np.array(ids_to_del, dtype=np.int64))
    new_meta = [m for i, m in enumerate(meta) if i not in ids_to_del]
    faiss.write_index(index, idx_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(new_meta, f, ensure_ascii=False, indent=2)
    print(f"Removed {len(ids_to_del)} memory entries from FAISS")
else:
    print("No memory entries found in FAISS")

# Wipe history.jsonl completely
open("logs/history.jsonl", "w").close()
print("Wiped logs/history.jsonl")

# Filter finetune_dataset.jsonl purely for anything involving "名前" and "記憶" or "覚え"
try:
    with open("logs/finetune_dataset.jsonl", "r") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        if "名前" in line or "記憶" in line or "覚え" in line:
            continue
        new_lines.append(line)
    with open("logs/finetune_dataset.jsonl", "w") as f:
        f.writelines(new_lines)
    print("Cleaned finetune_dataset.jsonl")
except Exception as e:
    pass
