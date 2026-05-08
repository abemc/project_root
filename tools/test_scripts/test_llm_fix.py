import sys
import os
from pathlib import Path

# プロジェクトルートをsys.pathに追加
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.rag.llm import call_llm

try:
    print("Testing call_llm with qwen2.5:7b...")
    response = call_llm("Hello, identify yourself.", model="qwen2.5:7b")
    print(f"Response: {response}")
except Exception as e:
    print(f"Error: {e}")
