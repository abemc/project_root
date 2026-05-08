import os
import sys
import time
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.rag.agent import RAGAgent
from src.rag.retriever import Retriever
from src.rag.reranker import Reranker

def benchmark_caching():
    print("Starting Performance Benchmark...")
    retriever = Retriever()
    reranker = Reranker()
    
    question = "RAGの信頼性を高めるための主要な戦略は何ですか？"
    
    # 1. キャッシュなしの状態での実行
    agent_cold = RAGAgent(question, retriever, reranker)
    # キャッシュをクリア
    agent_cold.cache_optimizer.clear_namespace("search_doc")
    
    print("\n--- Cold Start (No Cache) ---")
    start_time = time.time()
    # 検索アクションをシミュレーション
    res_cold = agent_cold._handle_search_doc(question)
    cold_duration = time.time() - start_time
    print(f"Result: {res_cold}")
    print(f"Duration: {cold_duration:.4f}s")
    
    # 2. キャッシュありの状態での実行
    agent_warm = RAGAgent(question, retriever, reranker)
    print("\n--- Warm Start (L2 Cache Hit) ---")
    start_time = time.time()
    res_warm = agent_warm._handle_search_doc(question)
    warm_duration = time.time() - start_time
    print(f"Result: {res_warm}")
    print(f"Duration: {warm_duration:.4f}s")
    
    # スピードアップ率
    speedup = (cold_duration / warm_duration) if warm_duration > 0 else float('inf')
    print(f"\n🚀 Speedup: {speedup:.2f}x")
    print(f"Latency Reduction: {((cold_duration - warm_duration) / cold_duration) * 100:.2f}%")

if __name__ == "__main__":
    benchmark_caching()
