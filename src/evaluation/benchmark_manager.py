#!/usr/bin/env python3
"""
統合ベンチマーク管理スクリプト

すべての5つのベンチマーク（MMLU、GSM8K、HumanEval、TruthfulQA、BBQ）
を統合的に管理・実行し、結果を統一フォーマットで記録します。

使用方法:
  python benchmark_manager.py --all                # 全ベンチマーク実行
  python benchmark_manager.py --benchmark mmlu     # 特定ベンチマークのみ
  python benchmark_manager.py --compare baseline.json current.json
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Callable
import argparse
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.evaluation.benchmark_runner import BenchmarkRunner, BenchmarkComparator
from src.evaluation.metrics.metric_calculator import MetricCalculator
from src.evaluation.datasets.mmlu_loader import MMULoader
from src.evaluation.datasets.gsm8k_loader import GSM8KLoader
from src.evaluation.datasets.humaneval_loader import HumanEvalLoader
from src.evaluation.datasets.truthfulqa_bbq_loaders import (
    TruthfulQALoader, BBQLoader
)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedBenchmarkManager:
    """
    統合ベンチマークマネージャー
    
    5つのベンチマークの読込・実行・結果管理を統一的に行います。
    """
    
    def __init__(
        self,
        model_name: str = "baseline-model",
        output_dir: str = "./results/benchmarks",
        num_samples: Optional[int] = None
    ):
        """
        初期化
        
        Args:
            model_name: モデル名
            output_dir: 結果出力ディレクトリ
            num_samples: デバッグ用サンプル数制限
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.num_samples = num_samples
        
        # ベンチマークランナー・メトリクス計算機
        self.runner = BenchmarkRunner(model_name, str(self.output_dir))
        self.calculator = MetricCalculator()
        
        # ローダー
        self.loaders = {
            'mmlu': MMULoader(num_samples=num_samples),
            'gsm8k': GSM8KLoader(num_samples=num_samples),
            'humaneval': HumanEvalLoader(num_samples=num_samples),
            'truthfulqa': TruthfulQALoader(num_samples=num_samples),
            'bbq': BBQLoader(num_samples=num_samples),
        }
        
        # 評価機
        self.evaluators = {
            'mmlu': None,  # 後で初期化
            'gsm8k': None,
            'humaneval': None,
            'truthfulqa': None,
            'bbq': None,
        }
        
        logger.info(f"Initialized UnifiedBenchmarkManager for model: {model_name}")
    
    def _get_dummy_inference_fn(self, benchmark_name: str) -> Callable:
        """
        デモ用推論関数を作成
        
        実際の推論ロジックに置き換える必要があります。
        
        Args:
            benchmark_name: ベンチマーク名
            
        Returns:
            推論関数
        """
        def dummy_inference(prompt: str) -> str:
            """ダミー推論: プロンプト長に基づいて答える"""
            if benchmark_name in ['mmlu']:
                options = ['A', 'B', 'C', 'D']
                return options[len(prompt) % 4]
            elif benchmark_name == 'gsm8k':
                return f"#### {len(prompt) % 100}"
            elif benchmark_name == 'humaneval':
                return "def dummy(): pass"
            elif benchmark_name == 'truthfulqa':
                return "Answer: " + "x" * (len(prompt) % 10)
            elif benchmark_name == 'bbq':
                return ['A', 'B', 'C'][len(prompt) % 3]
            return ""
        
        return dummy_inference
    
    def run_mmlu(self) -> Optional[Dict]:
        """MMUベンチマークを実行"""
        logger.info("Starting MMLU benchmark...")
        
        try:
            # データロード
            questions = self.loaders['mmlu'].load()
            
            if not questions:
                logger.warning("No MMLU questions loaded")
                return None
            
            # 推論実行
            predictions = []
            for q in questions[:min(len(questions), 100)]:  # デモなので100問のみ
                prompt, _ = self.loaders['mmlu'].format_for_model(q)
                pred = self._get_dummy_inference_fn('mmlu')(prompt)
                predictions.append(pred)
            
            # 評価
            references = [q.answer for q in questions[:len(predictions)]]
            
            result = self.runner.run_benchmark(
                benchmark_name="MMLU",
                task_type="classification",
                test_data=list(zip(predictions, references)),
                inference_fn=lambda x: x[0],  # 既に推論済み
                metric_fn=lambda pred, ref: self.calculator.compute_all_metrics(
                    [pred], [ref], "classification"
                ),
                description="Massive Multitask Language Understanding"
            )
            
            logger.info(f"MMLU completed: {result.metrics}")
            return result
            
        except Exception as e:
            logger.error(f"MMLU benchmark failed: {e}", exc_info=True)
            return None
    
    def run_gsm8k(self) -> Optional[Dict]:
        """GSM8Kベンチマークを実行"""
        logger.info("Starting GSM8K benchmark...")
        
        try:
            # データロード
            problems = self.loaders['gsm8k'].load()
            
            if not problems:
                logger.warning("No GSM8K problems loaded")
                return None
            
            # 推論実行（デモなので10問のみ）
            predictions = []
            for p in problems[:min(len(problems), 10)]:
                prompt = self.loaders['gsm8k'].format_for_model(p)
                pred = self._get_dummy_inference_fn('gsm8k')(prompt)
                predictions.append(pred)
            
            # 評価
            references = [p.answer for p in problems[:len(predictions)]]
            
            result = self.runner.run_benchmark(
                benchmark_name="GSM8K",
                task_type="math",
                test_data=list(zip(predictions, references)),
                inference_fn=lambda x: x[0],
                metric_fn=lambda pred, ref: self.calculator.compute_all_metrics(
                    [pred], [ref], "classification"
                ),
                description="Grade School Math"
            )
            
            logger.info(f"GSM8K completed: {result.metrics}")
            return result
            
        except Exception as e:
            logger.error(f"GSM8K benchmark failed: {e}", exc_info=True)
            return None
    
    def run_humaneval(self) -> Optional[Dict]:
        """HumanEvalベンチマークを実行"""
        logger.info("Starting HumanEval benchmark...")
        
        try:
            problems = self.loaders['humaneval'].load()
            
            if not problems:
                logger.warning("No HumanEval problems loaded")
                return None
            
            logger.info(f"HumanEval loaded: {len(problems)} problems")
            return None  # デモでは実行スキップ
            
        except Exception as e:
            logger.error(f"HumanEval benchmark failed: {e}", exc_info=True)
            return None
    
    def run_truthfulqa(self) -> Optional[Dict]:
        """TruthfulQAベンチマークを実行"""
        logger.info("Starting TruthfulQA benchmark...")
        
        try:
            questions = self.loaders['truthfulqa'].load()
            
            if not questions:
                logger.warning("No TruthfulQA questions loaded")
                return None
            
            logger.info(f"TruthfulQA loaded: {len(questions)} questions")
            return None  # デモでは実行スキップ
            
        except Exception as e:
            logger.error(f"TruthfulQA benchmark failed: {e}", exc_info=True)
            return None
    
    def run_bbq(self) -> Optional[Dict]:
        """BBQベンチマークを実行"""
        logger.info("Starting BBQ benchmark...")
        
        try:
            questions = self.loaders['bbq'].load()
            
            if not questions:
                logger.warning("No BBQ questions loaded")
                return None
            
            logger.info(f"BBQ loaded: {len(questions)} questions")
            return None  # デモでは実行スキップ
            
        except Exception as e:
            logger.error(f"BBQ benchmark failed: {e}", exc_info=True)
            return None
    
    def run_all(self) -> Dict[str, Optional[Dict]]:
        """すべてのベンチマークを実行"""
        logger.info("Running all benchmarks...")
        
        results = {}
        
        # 各ベンチマークを実行
        benchmarks = [
            ('mmlu', self.run_mmlu),
            ('gsm8k', self.run_gsm8k),
            ('humaneval', self.run_humaneval),
            ('truthfulqa', self.run_truthfulqa),
            ('bbq', self.run_bbq),
        ]
        
        for name, fn in benchmarks:
            try:
                results[name] = fn()
            except Exception as e:
                logger.error(f"Failed to run {name}: {e}")
                results[name] = None
        
        return results
    
    def run_specific(self, benchmark_name: str) -> Optional[Dict]:
        """特定のベンチマークを実行"""
        benchmark_name = benchmark_name.lower()
        
        run_methods = {
            'mmlu': self.run_mmlu,
            'gsm8k': self.run_gsm8k,
            'humaneval': self.run_humaneval,
            'truthfulqa': self.run_truthfulqa,
            'bbq': self.run_bbq,
        }
        
        if benchmark_name not in run_methods:
            logger.error(f"Unknown benchmark: {benchmark_name}")
            return None
        
        return run_methods[benchmark_name]()
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """結果をJSON形式で保存"""
        return self.runner.save_results(filename)
    
    def print_summary(self):
        """結果サマリーを表示"""
        self.runner.print_summary()


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='統合ベンチマーク管理スクリプト'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='すべてのベンチマークを実行'
    )
    parser.add_argument(
        '--benchmark',
        type=str,
        help='特定のベンチマークを実行 (mmlu|gsm8k|humaneval|truthfulqa|bbq)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='baseline-model',
        help='モデル名'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./results/benchmarks',
        help='結果出力ディレクトリ'
    )
    parser.add_argument(
        '--samples',
        type=int,
        help='デバッグ用サンプル数制限'
    )
    parser.add_argument(
        '--compare',
        nargs=2,
        metavar=('BASELINE', 'CURRENT'),
        help='2つの結果を比較'
    )
    
    args = parser.parse_args()
    
    # 比較モード
    if args.compare:
        baseline_file, current_file = args.compare
        logger.info(f"Comparing {baseline_file} vs {current_file}")
        
        try:
            comparator = BenchmarkComparator()
            result = comparator.compare_two_runs(baseline_file, current_file)
            comparator.print_comparison(result)
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return 1
        
        return 0
    
    # マネージャー初期化
    manager = UnifiedBenchmarkManager(
        model_name=args.model,
        output_dir=args.output,
        num_samples=args.samples
    )
    
    # ベンチマーク実行
    if args.all:
        logger.info("Running all benchmarks...")
        manager.run_all()
    elif args.benchmark:
        logger.info(f"Running {args.benchmark} benchmark...")
        manager.run_specific(args.benchmark)
    else:
        # デフォルト: MMLU + GSM8K
        logger.info("Running default benchmarks (MMLU, GSM8K)...")
        manager.run_mmlu()
        manager.run_gsm8k()
    
    # 結果表示・保存
    manager.print_summary()
    result_file = manager.save_results()
    logger.info(f"Results saved to: {result_file}")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
