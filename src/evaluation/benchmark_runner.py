"""
ベンチマーク統合実行エンジン

複数のベンチマーク（MMLU, GSM8K, HumanEval等）を統一的に実行・管理するモジュール
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from pathlib import Path
from tqdm import tqdm

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """ベンチマーク結果を保持するデータクラス"""
    benchmark_name: str
    task_type: str
    num_samples: int
    metrics: Dict[str, float]
    timestamp: str
    model_name: str = "default"
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return asdict(self)


class BenchmarkRunner:
    """ベンチマーク統合実行エンジン"""
    
    def __init__(self, model_name: str = "autonomous-llm", output_dir: str = "./results"):
        """
        初期化
        
        Args:
            model_name: モデル名
            output_dir: 結果出力ディレクトリ
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: List[BenchmarkResult] = []
        self.logger = logger
    
    def run_benchmark(self,
                     benchmark_name: str,
                     task_type: str,
                     test_data: List[Dict[str, Any]],
                     inference_fn: Callable[[str], str],
                     metric_fn: Callable[[List[str], List[str]], Dict[str, float]],
                     batch_size: int = 1,
                     description: str = "") -> BenchmarkResult:
        """
        単一ベンチマークを実行
        
        Args:
            benchmark_name: ベンチマーク名 (e.g., "MMLU", "GSM8K")
            task_type: タスク種別 (e.g., "classification", "math", "code")
            test_data: テストデータリスト（各要素は "question", "answer" を含む辞書）
            inference_fn: 推論関数（質問文 → 回答文）
            metric_fn: メトリクス計算関数（予測, 参照 → メトリクス辞書）
            batch_size: バッチサイズ
            description: 説明
            
        Returns:
            BenchmarkResult
        """
        self.logger.info(f"Starting benchmark: {benchmark_name}")
        
        predictions = []
        references = []
        
        # 推論実行
        with tqdm(total=len(test_data), desc=f"Running {benchmark_name}") as pbar:
            for i in range(0, len(test_data), batch_size):
                batch = test_data[i:i + batch_size]
                
                for sample in batch:
                    question = sample.get("question", "")
                    reference = sample.get("answer", "")
                    
                    try:
                        prediction = inference_fn(question)
                        predictions.append(prediction)
                        references.append(reference)
                    except Exception as e:
                        self.logger.error(f"Error during inference: {e}")
                        predictions.append("")
                        references.append(reference)
                    
                    pbar.update(1)
        
        # メトリクス計算
        self.logger.info(f"Computing metrics for {benchmark_name}")
        try:
            metrics = metric_fn(predictions, references)
        except Exception as e:
            self.logger.error(f"Error computing metrics: {e}")
            metrics = {}
        
        # 結果作成
        result = BenchmarkResult(
            benchmark_name=benchmark_name,
            task_type=task_type,
            num_samples=len(test_data),
            metrics=metrics,
            timestamp=datetime.now().isoformat(),
            model_name=self.model_name,
            notes=description
        )
        
        self.results.append(result)
        
        self.logger.info(f"Completed {benchmark_name}: {metrics}")
        
        return result
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """
        結果をJSONファイルに保存
        
        Args:
            filename: ファイル名（省略時は自動生成）
            
        Returns:
            保存ファイルパス
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        results_dict = {
            "model_name": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in self.results]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Results saved to {filepath}")
        
        return str(filepath)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        結果の概要を取得
        
        Returns:
            概要辞書
        """
        summary = {
            "model_name": self.model_name,
            "num_benchmarks": len(self.results),
            "benchmarks": {}
        }
        
        for result in self.results:
            summary["benchmarks"][result.benchmark_name] = {
                "task_type": result.task_type,
                "num_samples": result.num_samples,
                "metrics": result.metrics
            }
        
        return summary
    
    def print_summary(self) -> None:
        """
        結果の概要を表示
        """
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print(f"ベンチマーク結果概要 - モデル: {summary['model_name']}")
        print("="*80)
        
        for benchmark_name, benchmark_data in summary["benchmarks"].items():
            print(f"\n{benchmark_name}:")
            print(f"  タスク種別: {benchmark_data['task_type']}")
            print(f"  サンプル数: {benchmark_data['num_samples']}")
            print(f"  メトリクス:")
            for metric_name, metric_value in benchmark_data["metrics"].items():
                print(f"    {metric_name}: {metric_value:.4f}")
        
        print("\n" + "="*80)


class BenchmarkComparator:
    """複数のベンチマーク結果を比較するユーティリティ"""
    
    @staticmethod
    def load_results(filepath: str) -> Dict[str, Any]:
        """結果ファイルを読み込む"""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @staticmethod
    def compare_two_runs(baseline_path: str, current_path: str) -> Dict[str, Any]:
        """
        2つのベンチマーク実行結果を比較
        
        Args:
            baseline_path: ベースラインの結果ファイル
            current_path: 現在の結果ファイル
            
        Returns:
            比較結果
        """
        baseline = BenchmarkComparator.load_results(baseline_path)
        current = BenchmarkComparator.load_results(current_path)
        
        comparison = {
            "baseline_timestamp": baseline["timestamp"],
            "current_timestamp": current["timestamp"],
            "benchmarks": {}
        }
        
        for benchmark_name, baseline_bench in baseline["results"].items():
            if benchmark_name in current["results"]:
                current_bench = current["results"][benchmark_name]
                
                metrics_comparison = {}
                for metric_name, baseline_value in baseline_bench["metrics"].items():
                    current_value = current_bench["metrics"].get(metric_name, 0)
                    improvement = current_value - baseline_value
                    improvement_pct = (improvement / baseline_value * 100) if baseline_value != 0 else 0
                    
                    metrics_comparison[metric_name] = {
                        "baseline": baseline_value,
                        "current": current_value,
                        "improvement": improvement,
                        "improvement_pct": improvement_pct
                    }
                
                comparison["benchmarks"][benchmark_name] = metrics_comparison
        
        return comparison
    
    @staticmethod
    def print_comparison(comparison: Dict[str, Any]) -> None:
        """比較結果を表示"""
        print("\n" + "="*80)
        print(f"ベンチマーク比較")
        print(f"ベースライン: {comparison['baseline_timestamp']}")
        print(f"現在:         {comparison['current_timestamp']}")
        print("="*80)
        
        for benchmark_name, metrics in comparison["benchmarks"].items():
            print(f"\n{benchmark_name}:")
            for metric_name, values in metrics.items():
                print(f"  {metric_name}:")
                print(f"    ベースライン: {values['baseline']:.4f}")
                print(f"    現在:         {values['current']:.4f}")
                print(f"    改善:         {values['improvement']:+.4f} ({values['improvement_pct']:+.1f}%)")
        
        print("\n" + "="*80)
