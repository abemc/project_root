"""
Week 3 スケーリング検証 - 簡略化テスト
ローカルデータのみを使用した高速テスト
"""

import sys
from pathlib import Path
import time

# パスの追加
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from src.evaluation.scaling_benchmark import ScalingBenchmarkConfig
from src.evaluation.batch_inference import (
    BatchInferencePipeline,
    BatchInferenceConfig,
    DynamicBatchSizeOptimizer,
)


def test_batch_inference_simple():
    """バッチ推論パイプラインの簡単なテスト"""
    print("\n" + "="*70)
    print("🧪 Test 1: Simple Batch Inference Pipeline")
    print("="*70)
    
    # テストデータセット
    dataset = [
        {'id': i, 'text': f'Test item {i}', 'label': i % 4} for i in range(256)
    ]
    
    # 推論関数
    def simple_inference(item):
        # シミュレーションされた推論（遅延はなし）
        return f"Result_{item['id']}"
    
    # パイプライン実行
    config = BatchInferenceConfig(batch_size=32)
    pipeline = BatchInferencePipeline(config)
    
    print(f"Processing {len(dataset)} items with batch size {config.batch_size}")
    
    start_time = time.time()
    results = pipeline.process_batches_sequential(
        dataset,
        simple_inference,
    )
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ Processing completed in {elapsed_time:.3f}s")
    print(f"   Results: {len(results)} items processed")
    print(f"   Throughput: {len(results)/elapsed_time:.1f} items/sec")
    
    # キャッシュ統計
    cache_stats = pipeline.get_cache_statistics()
    print(f"\n📦 Cache Statistics:")
    print(f"   Cache hits: {cache_stats['cache_hits']}")
    print(f"   Cache misses: {cache_stats['cache_misses']}")
    print(f"   Hit rate: {cache_stats['hit_rate']:.2f}%")
    
    assert len(results) == len(dataset), "Result count mismatch"
    print(f"   ✅ All items processed successfully")


def test_batch_sizes():
    """異なるバッチサイズのテスト"""
    print("\n" + "="*70)
    print("🧪 Test 2: Batch Size Comparison")
    print("="*70)
    
    # テストデータセット
    dataset = [
        {'id': i, 'text': f'Test item {i}'} for i in range(1000)
    ]
    
    def simple_inference(item):
        return f"Result_{item['id']}"
    
    batch_sizes = [8, 16, 32, 64, 128]
    results_by_batch = {}
    
    for batch_size in batch_sizes:
        config = BatchInferenceConfig(batch_size=batch_size)
        pipeline = BatchInferencePipeline(config)
        
        start_time = time.time()
        results = pipeline.process_batches_sequential(dataset, simple_inference)
        elapsed_time = time.time() - start_time
        
        throughput = len(results) / elapsed_time
        results_by_batch[batch_size] = {
            'time': elapsed_time,
            'throughput': throughput,
        }
        
        print(f"  Batch size {batch_size:3d}: {elapsed_time:.3f}s | {throughput:7.1f} items/sec")
    
    # 最適なバッチサイズを特定
    best_batch = max(results_by_batch.items(), key=lambda x: x[1]['throughput'])
    print(f"\n✅ Optimal batch size: {best_batch[0]} ({best_batch[1]['throughput']:.1f} items/sec)")


def test_cache_effectiveness():
    """キャッシュの有効性テスト"""
    print("\n" + "="*70)
    print("🧪 Test 3: Cache Effectiveness")
    print("="*70)
    
    # 重複を含むテストデータセット
    dataset = [
        {'id': i, 'text': f'Item {i % 10}'} for i in range(100)
    ]
    
    def simple_inference(item):
        return f"Result_{item['text']}"
    
    config = BatchInferenceConfig(batch_size=16, enable_caching=True)
    pipeline = BatchInferencePipeline(config)
    
    print(f"Processing {len(dataset)} items (10 unique)")
    
    start_time = time.time()
    results = pipeline.process_batches_sequential(dataset, simple_inference)
    elapsed_time = time.time() - start_time
    
    # キャッシュ統計
    cache_stats = pipeline.get_cache_statistics()
    print(f"\n✅ Processing completed in {elapsed_time:.3f}s")
    print(f"   Results: {len(results)} items")
    print(f"   Cache hits: {cache_stats['cache_hits']}")
    print(f"   Cache misses: {cache_stats['cache_misses']}")
    print(f"   Hit rate: {cache_stats['hit_rate']:.2f}%")
    print(f"   Cache size: {cache_stats['cache_size']}")


def test_dynamic_optimization():
    """動的最適化のテスト"""
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
        (8, 0.8),    # batch_size=8, time=0.8s
        (16, 1.2),   # batch_size=16, time=1.2s
        (32, 2.0),   # batch_size=32, time=2.0s (best)
        (64, 4.5),   # batch_size=64, time=4.5s
        (128, 10.0), # batch_size=128, time=10.0s
    ]
    
    print("\nRecording batch performance:")
    for batch_size, inference_time in test_cases:
        optimizer.record_batch_performance(batch_size, inference_time)
        throughput = batch_size / inference_time
        print(f"  Batch {batch_size:3d}: {throughput:6.2f} items/sec")
    
    # 推奨バッチサイズ
    suggested = optimizer.suggest_batch_size()
    print(f"\n✅ Suggested batch size: {suggested}")
    
    # メモリに基づいた調整
    print(f"\nMemory-based adjustment:")
    
    # メモリ使用量が多い場合
    new_size = optimizer.adjust_batch_size(1950)  # 95%使用
    print(f"  High memory (95%): → {new_size}")
    
    # メモリに余裕がある場合
    prev_size = optimizer.batch_size
    new_size = optimizer.adjust_batch_size(800)  # 39%使用
    print(f"  Low memory (39%): {prev_size} → {new_size}")
    
    print(f"\n✅ Dynamic optimization test completed")


def test_configuration():
    """スケーリング検証設定のテスト"""
    print("\n" + "="*70)
    print("🧪 Test 5: Scaling Benchmark Configuration")
    print("="*70)
    
    config = ScalingBenchmarkConfig()
    
    print(f"\nBatch sizes:")
    for benchmark, size in config.batch_sizes.items():
        print(f"  {benchmark}: {size}")
    
    print(f"\nMemory limits (MB):")
    for benchmark, limit in config.memory_limits.items():
        print(f"  {benchmark}: {limit}")
    
    print(f"\nTimeouts (seconds):")
    for benchmark, timeout in config.timeouts.items():
        print(f"  {benchmark}: {timeout}s ({timeout/60:.1f}m)")
    
    print(f"\nOther settings:")
    print(f"  Number of workers: {config.num_workers}")
    print(f"  Sampling rate: {config.sampling_rate*100:.1f}%")
    
    print(f"\n✅ Configuration test completed")


def main():
    """メイン実行"""
    print("\n" + "="*70)
    print("🚀 Week 3 Scaling Verification - Simplified Test Suite")
    print("="*70)
    
    try:
        test_batch_inference_simple()
        test_batch_sizes()
        test_cache_effectiveness()
        test_dynamic_optimization()
        test_configuration()
        
        print("\n" + "="*70)
        print("✅ All Scaling Verification Tests Completed Successfully!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}", file=__import__('sys').stderr)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
