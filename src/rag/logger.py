import json
import datetime
from pathlib import Path

LOG_DIR = Path("logs")
JSONL_PATH = LOG_DIR / "history.jsonl"
READABLE_PATH = LOG_DIR / "history.md"

def save_history(state):
    LOG_DIR.mkdir(exist_ok=True)

    # JSONL形式で保存（データ分析用）
    with open(JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(state, ensure_ascii=False) + "\n")

    # Markdown形式で保存（閲覧用）
    _save_readable_log(state)

    return state

def _save_readable_log(state):
    timestamp = state.get("timestamp", datetime.datetime.now().isoformat())
    question = state.get("question", "（質問なし）")
    final_answer = state.get("final_answer", "（回答なし）")
    trace = state.get("trace", [])

    with open(READABLE_PATH, "a", encoding="utf-8") as f:
        f.write(f"# Executed at: {timestamp}\n")
        f.write(f"## Question\n{question}\n\n")
        
        if trace:
            f.write("## Execution Trace\n")
            for step_data in trace:
                step = step_data.get("step", "?")
                action = step_data.get("action", "Unknown")
                thought = step_data.get("thought", "")
                result = step_data.get("result", "")

                f.write(f"### Step {step}: {action}\n")
                if thought:
                    f.write(f"**Thought:**\n{thought}\n\n")
                f.write(f"**Result:**\n{result}\n\n")
        
        f.write("## Final Answer\n")
        f.write(f"{final_answer}\n")
        f.write("\n" + "="*40 + "\n\n")