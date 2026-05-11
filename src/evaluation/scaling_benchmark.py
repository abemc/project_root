"""
スケーリング検証マネージャー
大規模ベンチマークの実行・管理・最適化を行う
"""

import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScalingBenchmarkConfig:
    """スケーリング検証の設定"""
    
    def __init__(self):
        """デフォルト設定の初期化"""
        # バッチサイズ設定
        self.batch_sizes = {
            'mmlu': 32,      # MMLU: 32問/バッチ
            'gsm8k': 16,     # GSM8K: 16問/バッチ
            'humaneval': 8,
            'truthfulqa': 16,
            'bbq': 16,
        }
        
        # メモリ制限 (MB)
        self.memory_limits = {
            'mmlu': 2048,
            'gsm8k': 1024,
            'humaneval': 512,
        }
        
        # タイムアウト (秒)
        self.timeouts = {
            'mmlu': 3600,  # 1時間
            'gsm8k': 1800,  # 30分
            'humaneval': 900,  # 15分
        }
        
        # 推論並列数
        self.num_workers = 4
        
        # サンプリング率（テスト用: デフォルト100%）
        self.sampling_rate = 1.0


class ScalingBenchmarkRunner:
    """
    大規模ベンチマーク実行エンジン
    
    機能:
    - バッチ処理推論
    - メモリ効率化
    - 進捗追跡
    - 結果保存
    """
    
    def __init__(
        self,
        config: Optional[ScalingBenchmarkConfig] = None,
        results_dir: str = 'results/scaling_benchmarks'
    ):
        """
        初期化
        
        Args:
            config: スケーリング検証設定
            results_dir: 結果保存ディレクトリ
        """
        self.config = config or ScalingBenchmarkConfig()
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: Dict[str, Any] = {}
        self.current_benchmark: Optional[str] = None
        self.start_time: Optional[float] = None
    
    def run_scaling_benchmark(
        self,
        benchmark_name: str,
        dataset_loader_fn,  # 関数: ローダーインスタンスを返す
        inference_fn,  # 関数: 推論を実行
        metric_fn,  # 関数: メトリクスを計算
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        スケーリングベンチマークを実行
        
        Args:
            benchmark_name: ベンチマーク名 ('MMLU', 'GSM8K', など)
            dataset_loader_fn: データセットローダー関数
            inference_fn: 推論関数
            metric_fn: メトリクス計算関数
            limit: テスト用の問題数上限
            
        Returns:
            Dict: ベンチマーク結果
        """
        self.current_benchmark = benchmark_name
        self.start_time = time.time()
        
        logger.info(f"🚀 Starting scaling benchmark: {benchmark_name}")
        
        try:
            # データセット読み込み
            logger.info(f"📥 Loading {benchmark_name} dataset...")
            loader = dataset_loader_fn()
            dataset = loader.load()
            
            # limitを適用
            if limit is not None and len(dataset) > limit:
                dataset = dataset[:limit]
            
            if not dataset:
                logger.error(f"❌ No dataset loaded for {benchmark_name}")
                return {}
            
            dataset_size = len(dataset)
            logger.info(f"✅ Loaded {dataset_size} samples")
            
            # バッチ処理実行
            logger.info(f"🔄 Running batch inference (batch_size={self.config.batch_sizes.get(benchmark_name.lower(), 16)})")
            batch_size = self.config.batch_sizes.get(benchmark_name.lower(), 16)
            
            predictions = []
            references = []
            inference_times = []
            
            total_batches = (dataset_size + batch_size - 1) // batch_size
            
            for batch_idx in range(total_batches):
                batch_start_idx = batch_idx * batch_size
                batch_end_idx = min(batch_start_idx + batch_size, dataset_size)
                batch = dataset[batch_start_idx:batch_end_idx]
                
                # バッチ推論
                batch_start_time = time.time()
                batch_predictions = self._infer_batch(
                    batch, inference_fn, benchmark_name
                )
                batch_time = time.time() - batch_start_time
                inference_times.append(batch_time)
                
                predictions.extend(batch_predictions)
                references.extend([item.get('answer', item.get('choices', [''])[0]) for item in batch])
                
                # 進捗表示
                progress = (batch_idx + 1) / total_batches * 100
                avg_batch_time = sum(inference_times) / len(inference_times)
                logger.info(
                    f"  [{batch_idx+1:3d}/{total_batches}] "
                    f"Progress: {progress:5.1f}% | "
                    f"Avg batch time: {avg_batch_time:.2f}s"
                )
            
            # メトリクス計算
            logger.info("📊 Computing metrics...")
            metrics = metric_fn(predictions, references)
            
            # 結果集計
            elapsed_time = time.time() - self.start_time
            result = self._create_result_dict(
                benchmark_name,
                dataset_size,
                predictions,
                metrics,
                inference_times,
                elapsed_time,
            )
            
            self.results[benchmark_name] = result
            
            # 結果表示
            self._print_result_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in scaling benchmark: {e}", exc_info=True)
            return {}
    
    def _infer_batch(
        self,
        batch: List[Dict[str, Any]],
        inference_fn,
        benchmark_name: str,
    ) -> List[str]:
        """
        バッチの推論を実行
        
        Args:
            batch: 推論対象のバッチ
            inference_fn: 推論関数
            benchmark_name: ベンチマーク名
            
        Returns:
            List[str]: 予測結果
        """
        predictions = []
        
        for item in batch:
            try:
                if benchmark_name.upper() == 'MMLU':
                    # MMLU形式
                    prediction = inference_fn(
                        prompt=item.get('question', ''),
                        choices=item.get('choices', []),
                    )
                elif benchmark_name.upper() == 'GSM8K':
                    # GSM8K形式
                    prediction = inference_fn(
                        problem=item.get('problem', ''),
                    )
                else:
                    # 汎用形式
                    prediction = inference_fn(item)
                
                predictions.append(prediction)
            except Exception as e:
                logger.warning(f"  ⚠️  Inference failed for item: {e}")
                predictions.append('ERROR')
        
        return predictions
    
    def _create_result_dict(
        self,
        benchmark_name: str,
        dataset_size: int,
        predictions: List[str],
        metrics: Dict[str, float],
        inference_times: List[float],
        elapsed_time: float,
    ) -> Dict[str, Any]:
        """結果辞書を作成"""
        total_inference_time = sum(inference_times)
        
        return {
            'benchmark_name': benchmark_name,
            'timestamp': datetime.now().isoformat(),
            'dataset_size': dataset_size,
            'metrics': metrics,
            'inference_statistics': {
                'total_time': elapsed_time,
                'inference_time': total_inference_time,
                'avg_sample_time': total_inference_time / dataset_size if dataset_size > 0 else 0,
                'samples_per_second': dataset_size / total_inference_time if total_inference_time > 0 else 0,
                'batch_times': inference_times,
            },
            'predictions_count': len(predictions),
            'error_count': sum(1 for p in predictions if p == 'ERROR'),
        }
    
    def _print_result_summary(self, result: Dict[str, Any]):
        """結果の要約を表示"""
        print("\n" + "="*60)
        print(f"📊 Results: {result['benchmark_name']}")
        print("="*60)
        print(f"Dataset size: {result['dataset_size']} samples")
        print(f"Total time: {result['inference_statistics']['total_time']:.2f}s")
        print(f"Inference time: {result['inference_statistics']['inference_time']:.2f}s")
        print(f"Throughput: {result['inference_statistics']['samples_per_second']:.2f} samples/sec")
        print("\nMetrics:")
        for metric_name, value in result['metrics'].items():
            print(f"  {metric_name}: {value:.4f}")
        if result['error_count'] > 0:
            print(f"\n⚠️  Errors: {result['error_count']}/{result['predictions_count']}")
        print("="*60 + "\n")
    
    def save_results(self, filename: Optional[str] = None) -> Path:
        """
        結果をJSONで保存
        
        Args:
            filename: 保存ファイル名 (Noneの場合は自動生成)
            
        Returns:
            Path: 保存ファイルのパス
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'scaling_benchmark_results_{timestamp}.json'
        
        filepath = self.results_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Results saved to {filepath}")
        return filepath
    
    def compare_benchmarks(
        self,
        benchmark_names: List[str],
    ) -> Dict[str, Any]:
        """
        複数ベンチマークの結果を比較
        
        Args:
            benchmark_names: 比較するベンチマーク名リスト
            
        Returns:
            Dict: 比較結果
        """
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'benchmarks': {},
            'summary': {},
        }
        
        for name in benchmark_names:
            if name in self.results and self.results[name]:
                result = self.results[name]
                comparison['benchmarks'][name] = {
                    'metrics': result['metrics'],
                    'throughput': result['inference_statistics']['samples_per_second'],
                    'dataset_size': result['dataset_size'],
                }
        
        # 最良スコアの特定
        if comparison['benchmarks']:
            metrics_dict = {}
            for bench_name, metrics in comparison['benchmarks'].items():
                if metrics['metrics']:
                    metrics_dict[bench_name] = max(metrics['metrics'].values())
            
            if metrics_dict:
                best_benchmark = max(metrics_dict.items(), key=lambda x: x[1])
                comparison['summary']['best_accuracy'] = best_benchmark[0]
            
            best_throughput = max(
                comparison['benchmarks'].items(),
                key=lambda x: x[1]['throughput']
            )
            comparison['summary']['best_throughput'] = best_throughput[0]
        
        return comparison
    
    def get_scaling_statistics(self) -> Dict[str, Any]:
        """
        スケーリング統計情報を取得
        
        Returns:
            Dict: 統計情報
        """
        if not self.results:
            return {
                'total_benchmarks': 0,
                'total_samples': 0,
                'total_time': 0,
                'benchmarks': {},
            }
        
        stats = {
            'total_benchmarks': len(self.results),
            'total_samples': sum(r['dataset_size'] for r in self.results.values() if r),
            'total_time': sum(r['inference_statistics']['total_time'] for r in self.results.values() if r),
            'benchmarks': {},
        }
        
        for name, result in self.results.items():
            if result:  # 成功したベンチマークのみ
                stats['benchmarks'][name] = {
                    'samples': result['dataset_size'],
                    'throughput': result['inference_statistics']['samples_per_second'],
                    'best_metric': max(result['metrics'].values()) if result['metrics'] else 0,
                }
        
        return stats
