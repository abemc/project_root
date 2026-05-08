import json
import os
import shutil

# 擬似的な履歴データを作成
test_log = "logs/test_history.jsonl"
os.makedirs("logs", exist_ok=True)

data = [
    {
        "question": "地球の直径は？",
        "final_answer": "地球の赤道直径は約12,756kmです。",
        "feedback_status": "approved"
    },
    {
        "question": "月までの距離は？",
        "final_answer": "平均して約384,400kmです。",
        "feedback_status": "rejected"
    },
    {
        "question": "太陽系で一番大きい惑星は？",
        "final_answer": "木星です。",
        "feedback_status": "approved"
    }
]

with open(test_log, "w", encoding="utf-8") as f:
    for entry in data:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# dataset_generator をテスト
from src.rag.dataset_generator import generate_dataset

output_path = "logs/test_finetune_dataset.jsonl"
count, path = generate_dataset(log_path=test_log, output_path=output_path)

print(f"Extraction result: {count} samples extracted to {path}")

# 内容の確認
if count == 2:
    print("✅ Test Passed: 2 approved sessions extracted correctly.")
    with open(output_path, "r", encoding="utf-8") as f:
        print("Dataset Content (First line):")
        print(f.readline().strip())
else:
    print(f"❌ Test Failed: Expected 2 samples, but got {count}.")

# クリーンアップ
os.remove(test_log)
os.remove(output_path)
