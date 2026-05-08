# main.py
import torch
# Patch for torchao compatibility (torchao 0.16.0+ requires torch 2.5+, but we have 2.4.1)
if not hasattr(torch, "int1"):
    for i in range(1, 8):
        for dtype in [f"int{i}", f"uint{i}"]:
            setattr(torch, dtype, type(dtype, (), {})())

from src.rag.agent import run_agent
import os

if __name__ == "__main__":
    # Example question for testing
    question = "AIの役割は何ですか？"
    answer = run_agent(question)
    print(answer)