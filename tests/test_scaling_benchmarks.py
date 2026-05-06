"""
Week 3 スケーリング検証テスト
大規模ベンチマークの実行と最適化
"""

import sys
import os
from pathlib import Path
import time

# パスの追加
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.evaluation.scaling_benchmark import (
    ScalingBenchmarkRunner,
    ScalingBenchmarkConfig,
)
from src.evaluation.batch_inference import (
    BatchInferencePipeline,
    BatchInferenceConfig,
    DynamicBatchSizeOptimizer,
)
from src.evaluation.datasets.mmlu_loader import MMULoader
from src.evaluation.datasets.gsm8k_loader import GSM8KLoader
from src.evaluation.metrics.metric_calculator import MetricCalculator


def dummy_inference_mmlu(prompt: str, choices: list) -> str:
    """ダミー推論関数 (MMLU)"""
    # テスト用: ハッシュベースのダミー推論
    return choices[len(prompt) % len(choices)]


def dummy_inference_gsm8k(problem: str) -> str:
    """ダミー推論関数 (GSM8K)"""
    # テスト用: 問題テキストのハッシュから答えを生成
    return str((len(problem) * 17 + 42) % 100)


def test_scaling_benchmark_mmlu():
    """MMLU大規模ベンチマークテスト"""
    print("\n" + "="*70)
    print("🧪 Test 1: MMLU Scaling Benchmark")
    print("="*70)
    
    config = ScalingBenchmarkConfig()
    runner = ScalingBenchmarkRunner(config)
    
    # メトリクス計算関数
    calculator = MetricCalculator()
    
    def metric_fn(predictions, references):
        return calculator.compute_all_metrics(
            predictions, references, task_type='classification'
        )
    
    # ベンチマーク実行 (テスト用に100問に制限)
    result = runner.run_scaling_benchmark(
        benchmark_name='MMLU',
        dataset_loader_fn=lambda: MMULoader(),
        inference_fn=dummy_inference_mmlu,
        metric_fn=metric_fn,
        limit=100,  # テスト用
    )
    
    print("\n📊 Scaling Benchmark Results (MMLU):")
    if result:
        print(f"✅ Benchmark completed successfully")
        print(f"   Dataset size: {result['dataset_size']}")
        print(f"   Total time: {result['inference_statistics']['total_time']:.2f}s")
        print(f"   Throughput: {result['inference_statistics']['samples_per_second']:.2f} samples/sec")
    else:
        print(f"⚠️  Benchmark completed with warnings")
    
    return runner


def test_scaling_benchmark_gsm8k():
    """GSM8K大規模ベンチマークテスト"""
    print("\n" + "="*70)
    print("🧪 Test 2: GSM8K Scaling Benchmark")
    print("="*70)
    
    config = ScalingBenchmarkConfig()
    runner = ScalingBenchmarkRunner(config)
    
    # メトリクス計算関数
    calculator = MetricCalculator()
    
    def metric_fn(predictions, references):
        return calculator.compute_all_metrics(
            predictions, references, task_type='generation'
        )
    
    # ベンチマーク実行 (テスト用に50問に制限)
    result = runner.run_scaling_benchmark(
        benchmark_name='GSM8K',
        dataset_loader_fn=lambda: GSM8KLoader(),
        inference_fn=dummy_inference_gsm8k,
        metric_fn=metric_fn,
        limit=50,  # テスト用
    )
    
    print("\n📊 Scaling Benchmark Results (GSM8K):")
    if result:
        print(f"✅ Benchmark completed successfully")
        print(f"   Dataset size: {result['dataset_size']}")
        print(f"   Total time: {result['inference_statistics']['total_time']:.2f}s")
        print(f"   Throughput: {result['inference_statistics']['samples_per_second']:.2f} samples/sec")
    else:
        print(f"⚠️  Benchmark completed with warnings")
    
    return runner


def test_batch_inference_pipeline():
    """バッチ推論パイプラインテスト"""
    print("\n" + "="*70)
    print("🧪 Test 3: Batch Inference Pipeline")
    print("="*70)
    
    # テストデータセット
    dataset = [
        {'id': i, 'text': f'Test item {i}'} for i in range(100)
    ]
    
    # 推論関数
    def simple_inference(item):
        return f"Result_{item['id']}"
    
    # パイプライン実行
    config = BatchInferenceConfig(batch_size=16)
    pipeline = BatchInferencePipeline(config)
    
    print(f"Processing {len(dataset)} items with batch size {config.batch_size}")
    
    start_time = time.time()
    results = pipeline.process_batches_sequential(
        dataset,
        simple_inference,
        progress_callback=lambda c, t: print(f"  Progress: {c}/{t} batches")
    )
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ Processing completed in {elapsed_time:.2f}s")
    print(f"   Results: {len(results)} items processed")
    
    # キャッシュ統計
    cache_stats = pipeline.get_cache_statistics()
    print(f"\n📦 Cache Statistics:")
    print(f"   Cache hits: {cache_stats['cache_hits']}")
    print(f"   Cache misses: {cache_stats['cache_misses']}")
    print(f"   Hit rate: {cache_stats['hit_rate']:.2f}%")


def test_dynamic_batch_size_optimization():
    """動的バッチサイズ最適化テスト"""
    print("\n" + "="*70)
    print("🧪 Test 4: Dynamic Batch Size Optimization")
    print("="*70)
    
    optimizer = DynamicBatchSizeOptimizer(
        initial_batch_size=32,
        max_memory_mb=2048
    )
    
    print(f"Initial batch size: {optimizer.batch_size}")
    
    # パフォーマンスデータをシミュレート
    test_cases = [
        (16, 1.5),   # batch_size=16, time=1.5s
        (32, 2.5),   # batch_size=32, time=2.5s (best throughput)
        (64, 5.0),   # batch_size=64, time=5.0s
        (128, 11.0), # batch_size=128, time=11.0s
    ]
    
    print("\nRecording batch performance:")
    for batch_size, inference_time in test_cases:
        optimizer.record_batch_performance(batch_size, inference_time)
        throughput = batch_size / inference_time
        print(f"  Batch size {batch_size}: {throughput:.2f} items/sec")
    
    # 推奨バッチサイズ
    suggested = optimizer.suggest_batch_size()
    print(f"\n✅ Suggested batch size: {suggested}")
    
    # メモリに基づいた調整
    print(f"\nTesting memory-based adjustment:")
    initial_size = optimizer.batch_size
    
    # メモリ使用量が多い場合
    new_size = optimizer.adjust_batch_size(1950)  # 95%使用
    print(f"  High memory (95%): {initial_size} → {new_size}")
    
    # メモリに余裕がある場合
    initial_size = optimizer.batch_size
    new_size = optimizer.adjust_batch_size(800)  # 39%使用
    print(f"  Low memory (39%): {initial_size} → {new_size}")


def test_comparison_and_statistics():
    """ベンチマーク比較と統計テスト"""
    print("\n" + "="*70)
    print("🧪 Test 5: Benchmark Comparison & Statistics")
    print("="*70)
    
    config = ScalingBenchmarkConfig()
    runner = ScalingBenchmarkRunner(config)
    calculator = MetricCalculator()
    
    # 複数ベンチマークを実行
    benchmarks = [
        ('MMLU', MMULoader, dummy_inference_mmlu, 30),
        ('GSM8K', GSM8KLoader, dummy_inference_gsm8k, 20),
    ]
    
    for name, loader_cls, inference_fn, limit in benchmarks:
        def metric_fn(pred, ref):
            task_type = 'classification' if name == 'MMLU' else 'generation'
            return calculator.compute_all_metrics(pred, ref, task_type=task_type)
        
        runner.run_scaling_benchmark(
            benchmark_name=name,
            dataset_loader_fn=loader_cls,
            inference_fn=inference_fn,
            metric_fn=metric_fn,
            limit=limit,
        )
    
    # 比較
    comparison = runner.compare_benchmarks(['MMLU', 'GSM8K'])
    
    print("\n📊 Benchmark Comparison:")
    for bench_name, metrics in comparison['benchmarks'].items():
        print(f"\n  {bench_name}:")
        print(f"    Dataset size: {metrics['dataset_size']}")
        print(f"    Throughput: {metrics['throughput']:.2f} samples/sec")
        if metrics['metrics']:
            print(f"    Best metric: {max(metrics['metrics'].values()):.4f}")
    
    if comparison['summary']:
        print(f"\n  Summary:")
        print(f"    Best accuracy: {comparison['summary'].get('best_accuracy', 'N/A')}")
        print(f"    Best throughput: {comparison['summary'].get('best_throughput', 'N/A')}")
    
    # 統計情報
    stats = runner.get_scaling_statistics()
    print(f"\n📈 Scaling Statistics:")
    print(f"  Total benchmarks: {stats.get('total_benchmarks', 0)}")
    print(f"  Total samples: {stats.get('total_samples', 0)}")
    print(f"  Total time: {stats.get('total_time', 0):.2f}s")
    
    if stats.get('benchmarks'):
        print(f"\n  Benchmark details:")
        for bench_name, bench_stats in stats['benchmarks'].items():
            print(f"    {bench_name}: {bench_stats.get('samples', 0)} samples, {bench_stats.get('throughput', 0):.2f} samples/sec")
    
    # 結果保存
    runner.save_results('scaling_test_results.json')
    print(f"\n✅ Results saved to results/scaling_benchmarks/")


def main():
    """メイン実行"""
    print("\n" + "="*70)
    print("🚀 Week 3 Scaling Verification Test Suite")
    print("="*70)
    
    try:
        test_scaling_benchmark_mmlu()
        test_scaling_benchmark_gsm8k()
        test_batch_inference_pipeline()
        test_dynamic_batch_size_optimization()
        test_comparison_and_statistics()
        
        print("\n" + "="*70)
        print("✅ All Scaling Verification Tests Completed!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}", file=__import__('sys').stderr)
        raise


if __name__ == "__main__":
    main()
