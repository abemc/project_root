"""
Phase 5: Resource Optimizer
リソース最適化システム - トークン使用量、推論時間、コスト効率化

Components:
- ResourceMetrics: リソース使用量メトリクス
- TokenOptimizer: トークン最適化エンジン
- InferenceOptimizer: 推論パフォーマンス最適化
- BatchOptimizer: バッチ処理最適化
- ResourceOptimizer: 統合リソース最適化
"""

import json
import logging
import statistics
from typing import Dict, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import os

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """最適化戦略"""
    AGGRESSIVE = "aggressive"  # 最大削減
    BALANCED = "balanced"      # バランス型
    CONSERVATIVE = "conservative"  # 安全型
    COST_OPTIMIZED = "cost_optimized"  # コスト重視
    LATENCY_OPTIMIZED = "latency_optimized"  # レイテンシ重視


class TokenCategory(Enum):
    """トークンの分類"""
    PROMPT_TOKENS = "prompt_tokens"
    COMPLETION_TOKENS = "completion_tokens"
    VALIDATION_TOKENS = "validation_tokens"
    SYSTEM_TOKENS = "system_tokens"


@dataclass
class ResourceMetrics:
    """リソース使用量メトリクス"""
    timestamp: str
    total_tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    avg_tokens_per_request: float
    
    inference_time_ms: float  # 平均推論時間
    max_inference_time_ms: float
    min_inference_time_ms: float
    
    batch_size: int
    requests_processed: int
    
    memory_usage_mb: float
    cache_hit_ratio: float  # 0-1
    
    estimated_cost: float  # トークンあたりのコスト × 使用トークン数
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ResourceMetrics':
        return cls(**d)


@dataclass
class OptimizationResult:
    """最適化結果"""
    optimization_id: str
    strategy: OptimizationStrategy
    timestamp: str
    
    # 最適化前後の比較
    metrics_before: ResourceMetrics
    metrics_after: ResourceMetrics
    
    # 改善量
    token_reduction_percent: float
    latency_reduction_percent: float
    cost_reduction_percent: float
    
    # 推奨事項
    recommendations: List[str] = field(default_factory=list)
    applied_optimizations: List[str] = field(default_factory=list)
    
    success: bool = True
    
    def to_dict(self) -> Dict:
        d = {
            'optimization_id': self.optimization_id,
            'strategy': self.strategy.value,
            'timestamp': self.timestamp,
            'metrics_before': self.metrics_before.to_dict(),
            'metrics_after': self.metrics_after.to_dict(),
            'token_reduction_percent': self.token_reduction_percent,
            'latency_reduction_percent': self.latency_reduction_percent,
            'cost_reduction_percent': self.cost_reduction_percent,
            'recommendations': self.recommendations,
            'applied_optimizations': self.applied_optimizations,
            'success': self.success
        }
        return d


class TokenOptimizer:
    """トークン最適化エンジン"""
    
    def __init__(self, target_reduction: float = 0.2):
        """
        Args:
            target_reduction: 目標削減率 (0.2 = 20% 削減を目指す)
        """
        self.target_reduction = target_reduction
        self.optimization_history: List[Dict] = []
    
    def analyze_token_distribution(self, metrics_history: List[ResourceMetrics]) -> Dict[str, Any]:
        """トークン分布を分析"""
        if not metrics_history:
            return {}
        
        total_tokens = [m.total_tokens_used for m in metrics_history]
        prompt_tokens = [m.prompt_tokens for m in metrics_history]
        completion_tokens = [m.completion_tokens for m in metrics_history]
        
        return {
            'avg_total_tokens': statistics.mean(total_tokens),
            'avg_prompt_tokens': statistics.mean(prompt_tokens),
            'avg_completion_tokens': statistics.mean(completion_tokens),
            'prompt_to_completion_ratio': statistics.mean(prompt_tokens) / (statistics.mean(completion_tokens) + 1),
            'max_single_request': max(total_tokens),
            'min_single_request': min(total_tokens),
            'std_dev': statistics.stdev(total_tokens) if len(total_tokens) > 1 else 0
        }
    
    def suggest_prompt_optimization(self, current_prompt_tokens: int) -> List[str]:
        """プロンプト最適化の提案"""
        suggestions = []
        
        if current_prompt_tokens > 1000:
            suggestions.append("Prune unnecessary context from prompts (>1000 tokens)")
        
        if current_prompt_tokens > 500:
            suggestions.append("Use prompt templating to reduce redundancy")
            suggestions.append("Consider caching repeated prompts")
        
        suggestions.append("Use concise instruction wording")
        suggestions.append("Remove redundant role descriptions")
        
        return suggestions
    
    def suggest_completion_optimization(self, avg_completion_tokens: float) -> List[str]:
        """完了時間の最適化提案"""
        suggestions = []
        
        if avg_completion_tokens > 500:
            suggestions.append("Set lower max_tokens parameter")
            suggestions.append("Use stop sequences to terminate early")
        
        suggestions.append("Enable token budget enforcement")
        
        return suggestions
    
    def calculate_token_savings(
        self,
        current_metrics: ResourceMetrics,
        strategy: OptimizationStrategy
    ) -> Dict[str, float]:
        """トークン削減量を計算"""
        
        if strategy == OptimizationStrategy.AGGRESSIVE:
            reduction_factor = 0.30  # 30% 削減
        elif strategy == OptimizationStrategy.BALANCED:
            reduction_factor = 0.20  # 20% 削減
        elif strategy == OptimizationStrategy.CONSERVATIVE:
            reduction_factor = 0.10  # 10% 削減
        else:  # COST_OPTIMIZED, LATENCY_OPTIMIZED
            reduction_factor = 0.25  # 25% 削減
        
        new_prompt_tokens = int(current_metrics.prompt_tokens * (1 - reduction_factor))
        savings = current_metrics.prompt_tokens - new_prompt_tokens
        
        return {
            'current_tokens': float(current_metrics.prompt_tokens),
            'optimized_tokens': float(new_prompt_tokens),
            'savings': float(savings),
            'reduction_percent': reduction_factor * 100
        }


class InferenceOptimizer:
    """推論パフォーマンス最適化"""
    
    def __init__(self):
        self.inference_times: List[float] = []
    
    def record_inference_time(self, time_ms: float):
        """推論時間を記録"""
        self.inference_times.append(time_ms)
    
    def analyze_inference_performance(self) -> Dict[str, float]:
        """推論パフォーマンスを分析"""
        if not self.inference_times:
            return {}
        
        return {
            'avg_inference_time_ms': statistics.mean(self.inference_times),
            'median_inference_time_ms': statistics.median(self.inference_times),
            'p95_inference_time_ms': self._percentile(self.inference_times, 95),
            'p99_inference_time_ms': self._percentile(self.inference_times, 99),
            'max_inference_time_ms': max(self.inference_times),
            'min_inference_time_ms': min(self.inference_times),
            'std_dev_ms': statistics.stdev(self.inference_times) if len(self.inference_times) > 1 else 0
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """パーセンタイルを計算"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        lower = int(index)
        upper = lower + 1
        
        if upper >= len(sorted_data):
            return float(sorted_data[lower])
        
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight
    
    def suggest_latency_optimization(self, current_metrics: ResourceMetrics) -> List[str]:
        """レイテンシ最適化の提案"""
        suggestions = []
        
        if current_metrics.inference_time_ms > 1000:
            suggestions.append("Enable model quantization to reduce latency")
            suggestions.append("Consider using a smaller model variant")
        
        if current_metrics.inference_time_ms > 500:
            suggestions.append("Implement request batching")
            suggestions.append("Enable GPU acceleration")
        
        if current_metrics.cache_hit_ratio < 0.5:
            suggestions.append("Implement response caching")
            suggestions.append("Cache common completions")
        
        return suggestions


class BatchOptimizer:
    """バッチ処理最適化"""
    
    def __init__(self):
        self.batch_history: List[Dict] = []
    
    def analyze_batch_efficiency(self, metrics_history: List[ResourceMetrics]) -> Dict[str, Any]:
        """バッチ効率を分析"""
        if not metrics_history:
            return {}
        
        batch_sizes = [m.batch_size for m in metrics_history]
        tokens_per_batch = [
            m.total_tokens_used / max(m.batch_size, 1)
            for m in metrics_history
        ]
        
        return {
            'avg_batch_size': statistics.mean(batch_sizes),
            'max_batch_size': max(batch_sizes),
            'min_batch_size': min(batch_sizes),
            'avg_tokens_per_batch': statistics.mean(tokens_per_batch),
            'optimal_batch_size': self._calculate_optimal_batch_size(metrics_history)
        }
    
    def _calculate_optimal_batch_size(self, metrics_history: List[ResourceMetrics]) -> int:
        """最適バッチサイズを計算"""
        if not metrics_history:
            return 32
        
        # メモリ使用量とレイテンシのバランスを考慮
        avg_memory = statistics.mean([m.memory_usage_mb for m in metrics_history])
        avg_latency = statistics.mean([m.inference_time_ms for m in metrics_history])
        
        # ヒューリスティック: メモリ使用量の増加なく、レイテンシも許容範囲
        if avg_memory > 1000:
            return 16  # メモリ制約がある場合は小さめ
        elif avg_memory > 500:
            return 32
        elif avg_latency < 200:
            return 64  # レイテンシが低い場合はバッチを大きく
        else:
            return 32
    
    def suggest_batch_optimization(self, current_metrics: ResourceMetrics, analysis: Dict) -> List[str]:
        """バッチ最適化の提案"""
        suggestions = []
        
        optimal = analysis.get('optimal_batch_size', 32)
        current = current_metrics.batch_size
        
        if current < optimal * 0.5:
            suggestions.append(f"Increase batch size to {int(optimal)} for better GPU utilization")
        elif current > optimal * 1.5:
            suggestions.append(f"Reduce batch size to {int(optimal)} to avoid memory issues")
        
        if current_metrics.memory_usage_mb > 2000:
            suggestions.append("Use gradient accumulation to simulate larger batches")
            suggestions.append("Enable mixed precision training")
        
        return suggestions


class ResourceOptimizer:
    """統合リソース最適化システム"""
    
    def __init__(self, logs_dir: str = "logs/resource_optimization"):
        self.logs_dir = logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        
        self.token_optimizer = TokenOptimizer()
        self.inference_optimizer = InferenceOptimizer()
        self.batch_optimizer = BatchOptimizer()
        
        self.optimization_history: Dict[str, OptimizationResult] = {}
        self.metrics_history: List[ResourceMetrics] = []
        
        self._load_history()
    
    def _load_history(self):
        """最適化履歴を読み込み"""
        history_file = os.path.join(self.logs_dir, "optimization_history.jsonl")
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    for line in f:
                        result_dict = json.loads(line)
                        # Reconstruct OptimizationResult
                        result_dict['strategy'] = OptimizationStrategy(result_dict['strategy'])
                        result_dict['metrics_before'] = ResourceMetrics.from_dict(result_dict['metrics_before'])
                        result_dict['metrics_after'] = ResourceMetrics.from_dict(result_dict['metrics_after'])
                        result = OptimizationResult(**result_dict)
                        self.optimization_history[result.optimization_id] = result
                logger.info(f"Loaded {len(self.optimization_history)} optimization records")
            except Exception as e:
                logger.error(f"Failed to load optimization history: {e}")
    
    def _save_optimization_result(self, result: OptimizationResult):
        """最適化結果を保存"""
        history_file = os.path.join(self.logs_dir, "optimization_history.jsonl")
        try:
            self.optimization_history[result.optimization_id] = result
            with open(history_file, 'a') as f:
                f.write(json.dumps(result.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save optimization result: {e}")
    
    def record_metrics(self, metrics: ResourceMetrics):
        """メトリクスを記録"""
        self.metrics_history.append(metrics)
        self.inference_optimizer.record_inference_time(metrics.inference_time_ms)
        
        # メトリクス履歴をファイルに保存
        metrics_file = os.path.join(self.logs_dir, "metrics_history.jsonl")
        try:
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(metrics.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def run_optimization(
        self,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    ) -> OptimizationResult:
        """最適化を実行"""
        
        if not self.metrics_history:
            logger.warning("No metrics history available for optimization")
            return None
        
        current_metrics = self.metrics_history[-1]
        optimization_id = f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 各最適化プログラムを実行
        recommendations = []
        applied_optimizations = []
        
        # 1. トークン最適化
        self.token_optimizer.analyze_token_distribution(self.metrics_history)
        token_suggestions = self.token_optimizer.suggest_prompt_optimization(
            current_metrics.prompt_tokens
        )
        recommendations.extend(token_suggestions)
        applied_optimizations.extend(token_suggestions[:2])
        
        token_savings = self.token_optimizer.calculate_token_savings(
            current_metrics, strategy
        )
        
        # 2. 推論最適化
        self.inference_optimizer.analyze_inference_performance()
        latency_suggestions = self.inference_optimizer.suggest_latency_optimization(
            current_metrics
        )
        recommendations.extend(latency_suggestions)
        applied_optimizations.extend(latency_suggestions[:2])
        
        # 3. バッチ最適化
        batch_analysis = self.batch_optimizer.analyze_batch_efficiency(
            self.metrics_history
        )
        batch_suggestions = self.batch_optimizer.suggest_batch_optimization(
            current_metrics, batch_analysis
        )
        recommendations.extend(batch_suggestions)
        applied_optimizations.extend(batch_suggestions[:1])
        
        # 最適化後のメトリクスを推定
        estimated_after = ResourceMetrics(
            timestamp=datetime.now().isoformat(),
            total_tokens_used=int(current_metrics.total_tokens_used * (1 - token_savings['reduction_percent'] / 100)),
            prompt_tokens=int(token_savings['optimized_tokens']),
            completion_tokens=int(current_metrics.completion_tokens * 0.95),
            avg_tokens_per_request=current_metrics.avg_tokens_per_request * 0.90,
            inference_time_ms=current_metrics.inference_time_ms * 0.85,
            max_inference_time_ms=current_metrics.max_inference_time_ms * 0.85,
            min_inference_time_ms=current_metrics.min_inference_time_ms * 0.95,
            batch_size=int(batch_analysis.get('optimal_batch_size', current_metrics.batch_size)),
            requests_processed=current_metrics.requests_processed,
            memory_usage_mb=current_metrics.memory_usage_mb * 0.90,
            cache_hit_ratio=min(1.0, current_metrics.cache_hit_ratio * 1.2),
            estimated_cost=current_metrics.estimated_cost * 0.80
        )
        
        # 最適化結果を計算
        token_reduction = (
            (current_metrics.total_tokens_used - estimated_after.total_tokens_used) /
            max(current_metrics.total_tokens_used, 1)
        ) * 100
        
        latency_reduction = (
            (current_metrics.inference_time_ms - estimated_after.inference_time_ms) /
            max(current_metrics.inference_time_ms, 1)
        ) * 100
        
        cost_reduction = (
            (current_metrics.estimated_cost - estimated_after.estimated_cost) /
            max(current_metrics.estimated_cost, 1)
        ) * 100
        
        result = OptimizationResult(
            optimization_id=optimization_id,
            strategy=strategy,
            timestamp=datetime.now().isoformat(),
            metrics_before=current_metrics,
            metrics_after=estimated_after,
            token_reduction_percent=token_reduction,
            latency_reduction_percent=latency_reduction,
            cost_reduction_percent=cost_reduction,
            recommendations=recommendations,
            applied_optimizations=applied_optimizations,
            success=True
        )
        
        self._save_optimization_result(result)
        logger.info(f"Optimization completed: {optimization_id}")
        
        return result
    
    def get_optimization_recommendations(
        self,
        priority: str = "cost"  # "cost", "latency", "balanced"
    ) -> List[str]:
        """最適化の推奨事項を取得"""
        if not self.metrics_history:
            return []
        
        current_metrics = self.metrics_history[-1]
        recommendations = []
        
        if priority == "cost":
            recommendations.extend(
                self.token_optimizer.suggest_prompt_optimization(current_metrics.prompt_tokens)
            )
        elif priority == "latency":
            recommendations.extend(
                self.inference_optimizer.suggest_latency_optimization(current_metrics)
            )
        else:  # balanced
            recommendations.extend(
                self.token_optimizer.suggest_prompt_optimization(current_metrics.prompt_tokens)
            )
            recommendations.extend(
                self.inference_optimizer.suggest_latency_optimization(current_metrics)
            )
        
        return list(set(recommendations))  # Remove duplicates
    
    def get_optimization_history(self, limit: int = 10) -> List[OptimizationResult]:
        """最適化履歴を取得"""
        results = list(self.optimization_history.values())
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]
    
    def estimate_cost_savings(self, period_days: int = 30) -> Dict[str, float]:
        """コスト削減推定"""
        if not self.metrics_history:
            return {}
        
        # 過去のメトリクスから平均を計算
        recent_metrics = self.metrics_history[-min(period_days, len(self.metrics_history)):]
        avg_cost = statistics.mean([m.estimated_cost for m in recent_metrics])
        
        # 最適化で見込まれるコスト削減
        optimization_savings = 0.20  # 20% 削減を目指す
        
        return {
            'current_monthly_cost': avg_cost * (period_days / 1),
            'optimized_monthly_cost': avg_cost * (period_days / 1) * (1 - optimization_savings),
            'monthly_savings': avg_cost * (period_days / 1) * optimization_savings,
            'savings_percent': optimization_savings * 100,
            'annual_savings': avg_cost * (period_days / 1) * optimization_savings * 12
        }
