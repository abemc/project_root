import json
import faiss
import numpy as np

# 1. Clean history.jsonl
with open("logs/history.jsonl", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    try:
        data = json.loads(line)
        ans = data.get("final_answer", "")
        # Remove bad answers completely from logs
        if ans and ("iは" in ans or "iには" in ans or "iの名前" in ans or "覚えていません" in ans or "私には「オッサン」という名前を" in ans):
            continue
        new_lines.append(line)
    except:
        new_lines.append(line)

with open("logs/history.jsonl", "w") as f:
    f.writelines(new_lines)


# 2. Clean finetune_dataset.jsonl
try:
    with open("logs/finetune_dataset.jsonl", "r") as f:
        dpo_lines = f.readlines()

    new_dpo = []
    for line in dpo_lines:
        try:
            data = json.loads(line)
            content = json.dumps(data)
            if "iは" in content or "iには" in content or "iの名前" in content or "覚えていません" in content:
                continue
            new_dpo.append(line)
        except:
            pass

    with open("logs/finetune_dataset.jsonl", "w") as f:
        f.writelines(new_dpo)
except FileNotFoundError:
    pass

# 3. Clean FAISS corpus
try:
    from src.rag.retriever import Retriever
    ret = Retriever()
    ids_to_del = []
    
    for item in ret.meta:
        if item.get("meta", {}).get("source") == "memory" or item.get("source") == "memory":
            text = item.get("text", "")
            if "iは" in text or "iには" in text or "iの名前" in text or "覚えていません" in text or "私には「オッサン」という名前" in text:
                ids_to_del.append(item.get("id"))
                
    for failed_id in ids_to_del:
        ret.delete_document(failed_id)
        
    print(f"Removed {len(ids_to_del)} poisoned memories from FAISS")
except Exception as e:
    print("FAISS error:", e)

