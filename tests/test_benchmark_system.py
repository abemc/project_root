#!/usr/bin/env python3
"""
ベンチマーク測定体系のテスト・デモンストレーション

このスクリプトは、簡単なテストデータを使用してベンチマーク測定体系が
正常に動作することを確認します。
"""

import sys
from pathlib import Path

# プロジェクトパスを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.evaluation.benchmark_runner import BenchmarkRunner
from src.evaluation.metrics.metric_calculator import MetricCalculator


def simple_inference(question: str) -> str:
    """
    簡単な推論関数（デモ用）
    
    実際のモデルに置き換えることを想定
    """
    # ダミー実装：質問の長さに応じた回答を返す
    if "math" in question.lower():
        return "42"
    elif "capital" in question.lower():
        return "Tokyo"
    else:
        return "Unknown"


def create_dummy_datasets() -> dict:
    """ダミーデータセットを作成"""
    
    # MMLU-like データ
    mmlu_data = [
        {"question": "What is 2+2?", "answer": "4"},
        {"question": "What is 5*5?", "answer": "25"},
        {"question": "What is the capital of Japan?", "answer": "Tokyo"},
        {"question": "What is the capital of France?", "answer": "Paris"},
        {"question": "What is 10/2?", "answer": "5"},
    ]
    
    # GSM8K-like データ（数学）
    gsm8k_data = [
        {"question": "If you have 3 apples and 2 oranges, how many fruits do you have?", "answer": "5"},
        {"question": "What is 7*6?", "answer": "42"},
        {"question": "If John has 10 dollars and spends 3, how much does he have left?", "answer": "7"},
        {"question": "What is 100 divided by 4?", "answer": "25"},
        {"question": "If a triangle has sides 3, 4, 5, is it a right triangle?", "answer": "yes"},
    ]
    
    return {
        "mmlu": mmlu_data,
        "gsm8k": gsm8k_data,
    }


def test_metric_calculator():
    """メトリクス計算機能のテスト"""
    print("\n" + "="*80)
    print("メトリクス計算機能のテスト")
    print("="*80)
    
    calculator = MetricCalculator()
    
    # テストデータ
    predictions = ["4", "25", "Tokyo", "Paris", "5"]
    references = ["4", "25", "Tokyo", "Paris", "5"]
    
    # 完全一致テスト
    metrics = calculator.compute_all_metrics(predictions, references, task_type="classification")
    print("\n完全一致テスト:")
    print(f"  精度: {metrics['accuracy']:.4f}")
    print(f"  完全一致: {metrics['exact_match']:.4f}")
    
    # 部分一致テスト
    predictions_partial = ["4", "24", "Tokyo", "France", "5"]
    metrics_partial = calculator.compute_all_metrics(predictions_partial, references, task_type="classification")
    print("\n部分一致テスト:")
    print(f"  精度: {metrics_partial['accuracy']:.4f}")
    print(f"  F1スコア: {metrics_partial['f1']:.4f}")


def test_benchmark_runner():
    """ベンチマーク実行エンジンのテスト"""
    print("\n" + "="*80)
    print("ベンチマーク実行エンジンのテスト")
    print("="*80)
    
    # データセット作成
    datasets = create_dummy_datasets()
    
    # ベンチマーク実行
    runner = BenchmarkRunner(model_name="test-model", output_dir="./results/benchmarks")
    
    calculator = MetricCalculator()
    
    # MMLU ベンチマーク実行
    print("\nMMUベンチマークを実行中...")
    runner.run_benchmark(
        benchmark_name="MMLU",
        task_type="classification",
        test_data=datasets["mmlu"],
        inference_fn=simple_inference,
        metric_fn=lambda pred, ref: calculator.compute_all_metrics(pred, ref, "classification"),
        batch_size=1,
        description="Massive Multitask Language Understanding"
    )
    
    # GSM8K ベンチマーク実行
    print("\nGSM8Kベンチマークを実行中...")
    runner.run_benchmark(
        benchmark_name="GSM8K",
        task_type="math",
        test_data=datasets["gsm8k"],
        inference_fn=simple_inference,
        metric_fn=lambda pred, ref: calculator.compute_all_metrics(pred, ref, "classification"),
        batch_size=1,
        description="Grade School Math"
    )
    
    # 結果表示
    runner.print_summary()
    
    # 結果保存
    results_file = runner.save_results("baseline_metrics_test.json")
    print(f"\n✓ 結果を保存しました: {results_file}")
    
    return results_file


def main():
    """メイン処理"""
    print("\n" + "="*80)
    print("ベンチマーク測定体系のテスト・デモンストレーション")
    print("="*80)
    
    # メトリクス計算機能テスト
    test_metric_calculator()
    
    # ベンチマーク実行エンジンテスト
    test_benchmark_runner()
    
    print("\n" + "="*80)
    print("✓ テスト完了")
    print("="*80)
    print("\n次のステップ:")
    print("1. 実際のモデルを使用した推論関数を実装")
    print("2. 実際のMMRU, GSM8K等のデータセットを統合")
    print("3. ベースラインメトリクスを測定")
    print("4. 継続的改善を実施")


if __name__ == "__main__":
    main()
