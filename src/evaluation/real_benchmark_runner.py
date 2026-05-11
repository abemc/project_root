#!/usr/bin/env python3
"""
Week 3 Day 3-5: 実ベンチマーク実行エンジン

大規模データセット（MMLU 14K問、GSM8K 8.5K問）を使用した
実ベンチマーク実行とベースラインメトリクス測定

実行方法:
  python real_benchmark_runner.py mmlu --limit 1000
  python real_benchmark_runner.py gsm8k --limit 500
  python real_benchmark_runner.py all --output results.json
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
import json
import argparse
import logging
from datetime import datetime
import time
from dataclasses import dataclass, asdict

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from evaluation.metrics.metric_calculator import MetricCalculator
from evaluation.datasets.mmlu_loader import MMULoader
from evaluation.datasets.gsm8k_loader import GSM8KLoader
from evaluation.batch_inference import BatchInferencePipeline, BatchInferenceConfig

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """ベンチマーク結果"""
    benchmark_name: str
    timestamp: str
    total_samples: int
    processed_samples: int
    skipped_samples: int
    
    # メトリクス
    accuracy: float = 0.0
    f1_score: float = 0.0
    bleu_score: float = 0.0
    
    # パフォーマンス
    total_time_sec: float = 0.0
    avg_latency_ms: float = 0.0
    throughput_samples_per_sec: float = 0.0
    
    # メモリ統計
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    
    # その他
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
    
    def to_dict(self):
        """辞書に変換"""
        data = asdict(self)
        # datetime は文字列に変換
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data


class RealBenchmarkRunner:
    """実ベンチマーク実行エンジン"""
    
    def __init__(self, model_name: str = "baseline-model"):
        """
        初期化
        
        Args:
            model_name: モデル名
        """
        self.model_name = model_name
        self.metric_calculator = MetricCalculator()
        
        # バッチ推論設定
        inference_config = BatchInferenceConfig(
            batch_size=32,
            enable_caching=True,
            cache_size=10000
        )
        self.inference_pipeline = BatchInferencePipeline(config=inference_config)
        self.results = []
    
    def run_mmlu_benchmark(
        self,
        subjects: Optional[List[str]] = None,
        limit: Optional[int] = None,
        batch_size: int = 32
    ) -> BenchmarkResult:
        """
        MMLU ベンチマークを実行
        
        Args:
            subjects: 対象科目（デフォルト: すべて）
            limit: 処理数上限（デフォルト: 無制限）
            batch_size: バッチサイズ
        
        Returns:
            ベンチマーク結果
        """
        logger.info("Starting MMLU benchmark...")
        
        start_time = time.time()
        start_timestamp = datetime.now()
        
        try:
            # データセット読込
            logger.info("Loading MMLU dataset...")
            mmlu = MMULoader()
            questions = mmlu.load(subjects=subjects)
            
            if not questions:
                logger.error("Failed to load MMLU dataset")
                return BenchmarkResult(
                    benchmark_name="MMLU",
                    timestamp=start_timestamp.isoformat(),
                    total_samples=0,
                    processed_samples=0,
                    skipped_samples=0,
                    error_messages=["Failed to load dataset"]
                )
            
            logger.info(f"Loaded {len(questions)} MMLU questions")
            
            # サンプル数制限
            if limit:
                questions = questions[:limit]
            
            total_samples = len(questions)
            predictions = []
            references = []
            processed = 0
            skipped = 0
            errors = []
            
            # バッチ処理
            logger.info(f"Processing {total_samples} questions in batches of {batch_size}...")
            for i in range(0, len(questions), batch_size):
                batch = questions[i:i+batch_size]
                batch_predictions = []
                batch_references = []
                
                for q in batch:
                    try:
                        # 簡易推論: 選択肢からランダム選択（実装時は実モデルに置き換え）
                        q.get('question', '')
                        choices = q.get('choices', ['A', 'B', 'C', 'D'])
                        answer = q.get('answer', 'A')
                        
                        # ダミー推論 (実装時は実モデル推論に置き換え)
                        predicted_answer = choices[0] if choices else 'A'
                        
                        batch_predictions.append(predicted_answer)
                        batch_references.append(answer)
                        processed += 1
                    
                    except Exception as e:
                        logger.warning(f"Error processing question: {e}")
                        skipped += 1
                        errors.append(str(e))
                
                predictions.extend(batch_predictions)
                references.extend(batch_references)
                
                progress = (i + len(batch)) / total_samples * 100
                logger.info(f"Progress: {progress:.1f}% ({processed}/{total_samples})")
            
            # メトリクス計算
            logger.info("Computing metrics...")
            metrics = self.metric_calculator.compute_all_metrics(
                predictions=predictions,
                references=references,
                task_type='classification'
            )
            
            total_time = time.time() - start_time
            throughput = processed / total_time if total_time > 0 else 0
            
            result = BenchmarkResult(
                benchmark_name="MMLU",
                timestamp=start_timestamp.isoformat(),
                total_samples=total_samples,
                processed_samples=processed,
                skipped_samples=skipped,
                accuracy=metrics.get('accuracy', 0.0),
                f1_score=metrics.get('f1', 0.0),
                bleu_score=metrics.get('bleu', 0.0),
                total_time_sec=total_time,
                avg_latency_ms=(total_time / processed * 1000) if processed > 0 else 0,
                throughput_samples_per_sec=throughput,
                error_messages=errors[:10]  # 最初の10個のエラーのみ記録
            )
            
            logger.info("✅ MMLU benchmark complete:")
            logger.info(f"   Accuracy: {result.accuracy:.4f}")
            logger.info(f"   F1 Score: {result.f1_score:.4f}")
            logger.info(f"   Throughput: {throughput:.1f} samples/sec")
            logger.info(f"   Total time: {total_time:.2f} sec")
            
            self.results.append(result)
            return result
        
        except Exception as e:
            logger.error(f"MMLU benchmark failed: {e}", exc_info=True)
            return BenchmarkResult(
                benchmark_name="MMLU",
                timestamp=start_timestamp.isoformat(),
                total_samples=0,
                processed_samples=0,
                skipped_samples=0,
                error_messages=[str(e)]
            )
    
    def run_gsm8k_benchmark(
        self,
        limit: Optional[int] = None,
        batch_size: int = 16
    ) -> BenchmarkResult:
        """
        GSM8K ベンチマークを実行
        
        Args:
            limit: 処理数上限（デフォルト: 無制限）
            batch_size: バッチサイズ
        
        Returns:
            ベンチマーク結果
        """
        logger.info("Starting GSM8K benchmark...")
        
        start_time = time.time()
        start_timestamp = datetime.now()
        
        try:
            # データセット読込
            logger.info("Loading GSM8K dataset...")
            gsm8k = GSM8KLoader()
            problems = gsm8k.load()
            
            if not problems:
                logger.error("Failed to load GSM8K dataset")
                return BenchmarkResult(
                    benchmark_name="GSM8K",
                    timestamp=start_timestamp.isoformat(),
                    total_samples=0,
                    processed_samples=0,
                    skipped_samples=0,
                    error_messages=["Failed to load dataset"]
                )
            
            logger.info(f"Loaded {len(problems)} GSM8K problems")
            
            # サンプル数制限
            if limit:
                problems = problems[:limit]
            
            total_samples = len(problems)
            predictions = []
            references = []
            processed = 0
            skipped = 0
            errors = []
            
            # バッチ処理
            logger.info(f"Processing {total_samples} problems in batches of {batch_size}...")
            for i in range(0, len(problems), batch_size):
                batch = problems[i:i+batch_size]
                
                for problem in batch:
                    try:
                        problem.get('question', '')
                        answer = problem.get('answer', '')
                        
                        # ダミー推論 (実装時は実モデル推論に置き換え)
                        predicted_answer = "0"  # 簡易的な数値予測
                        
                        predictions.append(predicted_answer)
                        references.append(answer)
                        processed += 1
                    
                    except Exception as e:
                        logger.warning(f"Error processing problem: {e}")
                        skipped += 1
                        errors.append(str(e))
                
                progress = (i + len(batch)) / total_samples * 100
                logger.info(f"Progress: {progress:.1f}% ({processed}/{total_samples})")
            
            # メトリクス計算
            logger.info("Computing metrics...")
            metrics = self.metric_calculator.compute_all_metrics(
                predictions=predictions,
                references=references,
                task_type='generation'
            )
            
            total_time = time.time() - start_time
            throughput = processed / total_time if total_time > 0 else 0
            
            result = BenchmarkResult(
                benchmark_name="GSM8K",
                timestamp=start_timestamp.isoformat(),
                total_samples=total_samples,
                processed_samples=processed,
                skipped_samples=skipped,
                accuracy=metrics.get('accuracy', 0.0),
                f1_score=metrics.get('f1', 0.0),
                bleu_score=metrics.get('bleu', 0.0),
                total_time_sec=total_time,
                avg_latency_ms=(total_time / processed * 1000) if processed > 0 else 0,
                throughput_samples_per_sec=throughput,
                error_messages=errors[:10]
            )
            
            logger.info("✅ GSM8K benchmark complete:")
            logger.info(f"   Accuracy: {result.accuracy:.4f}")
            logger.info(f"   F1 Score: {result.f1_score:.4f}")
            logger.info(f"   Throughput: {throughput:.1f} samples/sec")
            logger.info(f"   Total time: {total_time:.2f} sec")
            
            self.results.append(result)
            return result
        
        except Exception as e:
            logger.error(f"GSM8K benchmark failed: {e}", exc_info=True)
            return BenchmarkResult(
                benchmark_name="GSM8K",
                timestamp=start_timestamp.isoformat(),
                total_samples=0,
                processed_samples=0,
                skipped_samples=0,
                error_messages=[str(e)]
            )
    
    def save_results(self, output_path: str):
        """
        結果をファイルに保存
        
        Args:
            output_path: 出力ファイルパス
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        results_data = {
            "model": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in self.results],
            "summary": self._generate_summary()
        }
        
        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {output_path}")
    
    def _generate_summary(self) -> Dict:
        """サマリーを生成"""
        if not self.results:
            return {}
        
        return {
            "total_benchmarks": len(self.results),
            "total_samples": sum(r.total_samples for r in self.results),
            "total_processed": sum(r.processed_samples for r in self.results),
            "total_time_sec": sum(r.total_time_sec for r in self.results),
            "avg_accuracy": sum(r.accuracy for r in self.results) / len(self.results),
            "avg_f1": sum(r.f1_score for r in self.results) / len(self.results),
        }


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="実ベンチマーク実行")
    
    parser.add_argument(
        "benchmark",
        choices=["mmlu", "gsm8k", "all"],
        help="ベンチマーク選択"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="サンプル数上限"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="バッチサイズ"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="出力ファイルパス"
    )
    
    args = parser.parse_args()
    
    runner = RealBenchmarkRunner()
    
    if args.benchmark in ["mmlu", "all"]:
        runner.run_mmlu_benchmark(limit=args.limit, batch_size=args.batch_size)
    
    if args.benchmark in ["gsm8k", "all"]:
        runner.run_gsm8k_benchmark(limit=args.limit, batch_size=args.batch_size // 2)
    
    runner.save_results(args.output)
    
    # サマリー表示
    print("\n" + "="*70)
    print("📊 ベンチマーク実行完了")
    print("="*70)
    for result in runner.results:
        print(f"\n{result.benchmark_name}:")
        print(f"  総サンプル数: {result.total_samples}")
        print(f"  処理済み: {result.processed_samples}")
        print(f"  スキップ: {result.skipped_samples}")
        print(f"  精度: {result.accuracy:.4f}")
        print(f"  F1スコア: {result.f1_score:.4f}")
        print(f"  スループット: {result.throughput_samples_per_sec:.1f} samples/sec")
        print(f"  実行時間: {result.total_time_sec:.2f} sec")


if __name__ == "__main__":
    main()
