import json
import os

def generate_dataset(log_path="logs/history.jsonl", output_path="logs/finetune_dataset.jsonl"):
    """
    承認された対話履歴から、ファインチューニング用のデータセットを生成する。
    """
    if not os.path.exists(log_path):
        return 0, log_path

    dataset = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                # 承認されたセッションのみを抽出
                if data.get("feedback_status") == "approved":
                    question = data.get("question")
                    answer = data.get("final_answer")
                    
                    if not question or not answer:
                        continue
                    
                    # Qwen2.5 / Unsloth 形式のメッセージに変換
                    # ここではシンプルに ユーザー vs アシスタント の形式
                    # 必要に応じてトレース（思考プロセス）をシステムプロンプトや思考タグに入れる
                    message = {
                        "messages": [
                            {"role": "user", "content": question},
                            {"role": "assistant", "content": answer}
                        ]
                    }
                    dataset.append(message)
            except Exception:
                continue

    if dataset:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in dataset:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return len(dataset), output_path
    
    return 0, output_path

def get_approved_count(log_path="logs/history.jsonl"):
    """
    承認されたセッションの総数を返す。
    """
    if not os.path.exists(log_path):
        return 0
    
    count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("feedback_status") == "approved":
                    count += 1
            except Exception:
                continue
    return count

def generate_dpo_dataset(log_path="logs/history.jsonl", output_path="logs/dpo_dataset.jsonl"):
    """
    承認された対話履歴と拒否された回答から、DPO学習用データセットを生成する。
    """
    if not os.path.exists(log_path):
        return 0, log_path

    dataset = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("feedback_status") == "approved":
                    question = data.get("question")
                    chosen_answer = data.get("final_answer")
                    rejected_answers = data.get("rejected_answers", [])
                    
                    if not question or not chosen_answer or not rejected_answers:
                        continue
                    
                    rejected_answer = rejected_answers[-1]
                    dpo_entry = {
                        "prompt": question,
                        "chosen": chosen_answer,
                        "rejected": rejected_answer
                    }
                    dataset.append(dpo_entry)
            except Exception:
                continue

    if dataset:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in dataset:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return len(dataset), output_path
    
    return 0, output_path

def get_dpo_count(log_path="logs/history.jsonl"):
    """
    DPO用に利用可能なセッション数（承認済みかつ拒否履歴あり）を返す。
    """
    if not os.path.exists(log_path):
        return 0
    
    count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("feedback_status") == "approved" and data.get("rejected_answers"):
                    count += 1
            except Exception:
                continue
    return count

if __name__ == "__main__":
    count, path = generate_dataset()
    print(f"Extracted {count} approved sessions into {path}")
