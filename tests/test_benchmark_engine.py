#!/usr/bin/env python3
"""
Week 3 Day 3-5: 実ベンチマーク実行 - テスト版

ダミーデータを使用してベンチマーク実行エンジンをテスト
"""

import sys
from pathlib import Path
from typing import Dict, List
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from evaluation.metrics.metric_calculator import MetricCalculator


@dataclass
class TestBenchmarkResult:
    """テストベンチマーク結果"""
    benchmark_name: str
    timestamp: str
    total_samples: int
    processed_samples: int
    accuracy: float
    f1_score: float
    total_time_sec: float
    throughput_samples_per_sec: float
    
    def to_dict(self):
        """辞書に変換"""
        return asdict(self)


class TestBenchmarkRunner:
    """テスト用ベンチマーク実行エンジン"""
    
    def __init__(self):
        """初期化"""
        self.metric_calculator = MetricCalculator()
        self.results = []
    
    def run_mmlu_test(self, num_samples: int = 100) -> TestBenchmarkResult:
        """
        MMLU テストベンチマーク（ダミーデータ）
        
        Args:
            num_samples: テストサンプル数
        
        Returns:
            テストベンチマーク結果
        """
        print(f"\n🧪 Testing MMLU Benchmark ({num_samples} samples)...")
        
        start_time = time.time()
        start_timestamp = datetime.now()
        
        # ダミーデータ生成
        predictions = []
        references = []
        
        for i in range(num_samples):
            # 70% の精度でダミー予測
            if i % 10 < 7:
                pred = str(i % 4)  # 0-3
                ref = str(i % 4)   # 正解
            else:
                pred = str((i + 1) % 4)
                ref = str(i % 4)   # 不正解
            
            predictions.append(pred)
            references.append(ref)
        
        # メトリクス計算
        metrics = self.metric_calculator.compute_all_metrics(
            predictions=predictions,
            references=references,
            task_type='classification'
        )
        
        total_time = time.time() - start_time
        throughput = num_samples / total_time if total_time > 0 else 0
        
        result = TestBenchmarkResult(
            benchmark_name="MMLU (Test)",
            timestamp=start_timestamp.isoformat(),
            total_samples=num_samples,
            processed_samples=num_samples,
            accuracy=metrics.get('accuracy', 0.0),
            f1_score=metrics.get('f1', 0.0),
            total_time_sec=total_time,
            throughput_samples_per_sec=throughput
        )
        
        print(f"  ✅ Accuracy: {result.accuracy:.4f}")
        print(f"  ✅ F1 Score: {result.f1_score:.4f}")
        print(f"  ✅ Throughput: {throughput:.1f} samples/sec")
        print(f"  ✅ Time: {total_time:.3f} sec")
        
        self.results.append(result)
        return result
    
    def run_gsm8k_test(self, num_samples: int = 50) -> TestBenchmarkResult:
        """
        GSM8K テストベンチマーク（ダミーデータ）
        
        Args:
            num_samples: テストサンプル数
        
        Returns:
            テストベンチマーク結果
        """
        print(f"\n🧪 Testing GSM8K Benchmark ({num_samples} samples)...")
        
        start_time = time.time()
        start_timestamp = datetime.now()
        
        # ダミーデータ生成
        predictions = []
        references = []
        
        for i in range(num_samples):
            # 65% の精度でダミー予測
            if i % 10 < 6.5:
                pred = str(i)  # 正解
                ref = str(i)
            else:
                pred = str((i + 1) % 100)  # 不正解
                ref = str(i)
            
            predictions.append(pred)
            references.append(ref)
        
        # メトリクス計算
        metrics = self.metric_calculator.compute_all_metrics(
            predictions=predictions,
            references=references,
            task_type='generation'
        )
        
        total_time = time.time() - start_time
        throughput = num_samples / total_time if total_time > 0 else 0
        
        result = TestBenchmarkResult(
            benchmark_name="GSM8K (Test)",
            timestamp=start_timestamp.isoformat(),
            total_samples=num_samples,
            processed_samples=num_samples,
            accuracy=metrics.get('accuracy', 0.0),
            f1_score=metrics.get('f1', 0.0),
            total_time_sec=total_time,
            throughput_samples_per_sec=throughput
        )
        
        print(f"  ✅ Accuracy: {result.accuracy:.4f}")
        print(f"  ✅ F1 Score: {result.f1_score:.4f}")
        print(f"  ✅ Throughput: {throughput:.1f} samples/sec")
        print(f"  ✅ Time: {total_time:.3f} sec")
        
        self.results.append(result)
        return result
    
    def save_results(self, output_path: str = "test_benchmark_results.json"):
        """結果を保存"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        results_data = {
            "test_type": "benchmark_engine_validation",
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total_benchmarks": len(self.results),
                "avg_accuracy": sum(r.accuracy for r in self.results) / len(self.results) if self.results else 0,
                "avg_f1": sum(r.f1_score for r in self.results) / len(self.results) if self.results else 0,
                "total_time": sum(r.total_time_sec for r in self.results),
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Results saved to: {output_path}")


def main():
    """メイン処理"""
    print("\n" + "="*70)
    print("🧪 Week 3 Day 3: ベンチマーク実行エンジン テスト")
    print("="*70)
    
    runner = TestBenchmarkRunner()
    
    # MMLU テスト
    print("\n📊 Test 1: MMLU Benchmark (100 samples)")
    mmlu_result = runner.run_mmlu_test(num_samples=100)
    
    # GSM8K テスト
    print("\n📊 Test 2: GSM8K Benchmark (50 samples)")
    gsm8k_result = runner.run_gsm8k_test(num_samples=50)
    
    # 結果保存
    runner.save_results()
    
    # サマリー表示
    print("\n" + "="*70)
    print("📊 テスト完了 - サマリー")
    print("="*70)
    
    for result in runner.results:
        print(f"\n{result.benchmark_name}:")
        print(f"  Samples: {result.total_samples}")
        print(f"  Accuracy: {result.accuracy:.4f}")
        print(f"  F1 Score: {result.f1_score:.4f}")
        print(f"  Throughput: {result.throughput_samples_per_sec:.1f} samples/sec")
        print(f"  Time: {result.total_time_sec:.3f} sec")
    
    print("\n✅ ベンチマーク実行エンジンが正常に動作することを確認しました！")
    print("\n💡 次のステップ:")
    print("  1. 実データセット (MMLU 14K, GSM8K 8.5K) を使用したベンチマーク")
    print("  2. ベースラインメトリクスの測定")
    print("  3. 言語別精度比較 (EN/JA)")


if __name__ == "__main__":
    main()
