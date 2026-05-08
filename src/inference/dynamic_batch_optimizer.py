# -*- coding: utf-8 -*-
"""
動的バッチ最適化 V2
Phase 12 Task 3

AI 駆動型バッチサイズ最適化・SLA 対応
目標: スループット 20-30% 向上
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import asyncio
from collections import deque
import math


# ============================================================================
# Enums & Data Classes
# ============================================================================

class OptimizationStrategy(Enum):
    """最適化戦略"""
    THROUGHPUT = "throughput"      # スループット最大化
    LATENCY = "latency"            # レイテンシ最小化
    BALANCED = "balanced"          # バランス型
    SLA_AWARE = "sla_aware"        # SLA 対応型


class BatchSizeRecommendation(Enum):
    """バッチサイズ推奨"""
    INCREASE = "increase"          # 増加推奨
    DECREASE = "decrease"          # 削減推奨
    MAINTAIN = "maintain"          # 維持推奨


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    timestamp: float
    batch_size: int
    throughput_req_per_sec: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    memory_used_mb: float
    gpu_utilization_percent: float
    power_consumption_w: float
    queueing_latency_ms: float = 0.0
    
    @property
    def efficiency_score(self) -> float:
        """効率スコア (スループット/レイテンシ)"""
        if self.avg_latency_ms == 0:
            return 0.0
        return self.throughput_req_per_sec / (self.avg_latency_ms / 1000.0)


@dataclass
class SLATarget:
    """SLA 目標"""
    p95_latency_ms: float = 10.0      # 95% で 10ms 以下
    p99_latency_ms: float = 20.0      # 99% で 20ms 以下
    min_throughput: float = 10000.0   # 最小スループット
    max_power_w: float = 350.0        # 最大消費電力


@dataclass
class DynamicBatchConfig:
    """動的バッチ設定"""
    min_batch_size: int = 1
    max_batch_size: int = 128
    initial_batch_size: int = 32
    target_latency_ms: float = 10.0
    target_throughput: float = 50000.0
    adjustment_step: int = 4         # バッチサイズ調整ステップ
    history_window: int = 100        # 履歴ウィンドウ
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.SLA_AWARE
    sla_target: SLATarget = field(default_factory=SLATarget)
    enable_prediction: bool = True
    enable_feedback: bool = True


# ============================================================================
# Batch Size Predictor
# ============================================================================

class BatchSizePredictor:
    """バッチサイズ予測エンジン"""
    
    def __init__(self, config: DynamicBatchConfig):
        self.config = config
        self.history: deque = deque(maxlen=config.history_window)
        self.predictions: Dict[int, Dict] = {}
    
    def add_observation(self, metrics: PerformanceMetrics):
        """観測データ追加"""
        self.history.append(metrics)
    
    def predict_performance(self, batch_size: int) -> Dict:
        """バッチサイズのパフォーマンス予測"""
        
        # 履歴からの線形補間
        sorted_history = sorted(self.history, key=lambda x: x.batch_size)
        
        if not sorted_history:
            return self._default_prediction(batch_size)
        
        # 最も近い 2 つのデータポイントを探す
        lower_point = None
        upper_point = None
        
        for point in sorted_history:
            if point.batch_size <= batch_size:
                lower_point = point
            if point.batch_size >= batch_size and upper_point is None:
                upper_point = point
        
        if lower_point is None:
            lower_point = sorted_history[0]
        if upper_point is None:
            upper_point = sorted_history[-1]
        
        # 線形補間
        if lower_point.batch_size == upper_point.batch_size:
            pred_throughput = lower_point.throughput_req_per_sec
            pred_latency = lower_point.avg_latency_ms
        else:
            ratio = (batch_size - lower_point.batch_size) / \
                   (upper_point.batch_size - lower_point.batch_size)
            
            pred_throughput = lower_point.throughput_req_per_sec + \
                            (upper_point.throughput_req_per_sec - lower_point.throughput_req_per_sec) * ratio
            pred_latency = lower_point.avg_latency_ms + \
                          (upper_point.avg_latency_ms - lower_point.avg_latency_ms) * ratio
        
        return {
            "batch_size": batch_size,
            "predicted_throughput": pred_throughput,
            "predicted_latency": pred_latency,
            "confidence": 0.7 + (0.3 * min(len(self.history), 10) / 10.0),
        }
    
    def _default_prediction(self, batch_size: int) -> Dict:
        """デフォルト予測"""
        # 簡単な推定モデル
        base_throughput = 5000.0  # req/sec per GPU
        base_latency = 5.0  # ms
        
        return {
            "batch_size": batch_size,
            "predicted_throughput": base_throughput * math.sqrt(batch_size),
            "predicted_latency": base_latency * math.log2(batch_size + 1),
            "confidence": 0.3,
        }


# ============================================================================
# SLA Compliance Monitor
# ============================================================================

class SLAComplianceMonitor:
    """SLA コンプライアンスモニター"""
    
    def __init__(self, sla_target: SLATarget):
        self.sla_target = sla_target
        self.violations: List[Dict] = []
        self.compliance_history: deque = deque(maxlen=1000)
    
    def check_compliance(self, metrics: PerformanceMetrics) -> Dict:
        """SLA コンプライアンスチェック"""
        
        violations = []
        compliance_score = 1.0
        
        # P95 レイテンシチェック
        if metrics.p95_latency_ms > self.sla_target.p95_latency_ms:
            violations.append({
                "metric": "p95_latency",
                "target": self.sla_target.p95_latency_ms,
                "actual": metrics.p95_latency_ms,
                "severity": "high",
            })
            compliance_score *= 0.8
        
        # P99 レイテンシチェック
        if metrics.p99_latency_ms > self.sla_target.p99_latency_ms:
            violations.append({
                "metric": "p99_latency",
                "target": self.sla_target.p99_latency_ms,
                "actual": metrics.p99_latency_ms,
                "severity": "critical",
            })
            compliance_score *= 0.7
        
        # スループットチェック
        if metrics.throughput_req_per_sec < self.sla_target.min_throughput:
            violations.append({
                "metric": "throughput",
                "target": self.sla_target.min_throughput,
                "actual": metrics.throughput_req_per_sec,
                "severity": "high",
            })
            compliance_score *= 0.8
        
        # 消費電力チェック
        if metrics.power_consumption_w > self.sla_target.max_power_w:
            violations.append({
                "metric": "power_consumption",
                "target": self.sla_target.max_power_w,
                "actual": metrics.power_consumption_w,
                "severity": "medium",
            })
            compliance_score *= 0.9
        
        result = {
            "is_compliant": len(violations) == 0,
            "compliance_score": compliance_score,
            "violations": violations,
            "metrics_analyzed": [
                "p95_latency", "p99_latency", "throughput", "power_consumption"
            ]
        }
        
        self.compliance_history.append(result)
        if violations:
            self.violations.extend(violations)
        
        return result
    
    def get_compliance_stats(self) -> Dict:
        """コンプライアンス統計"""
        if not self.compliance_history:
            return {"compliant_percent": 100.0}
        
        compliant_count = sum(1 for r in self.compliance_history if r["is_compliant"])
        avg_compliance_score = np.mean([r["compliance_score"] for r in self.compliance_history])
        
        return {
            "compliant_percent": (compliant_count / len(self.compliance_history)) * 100,
            "avg_compliance_score": avg_compliance_score,
            "total_violations": len(self.violations),
            "critical_violations": sum(
                1 for v in self.violations if v["severity"] == "critical"
            ),
        }


# ============================================================================
# Feedback Loop
# ============================================================================

class FeedbackLoop:
    """フィードバックループ"""
    
    def __init__(self, config: DynamicBatchConfig):
        self.config = config
        self.adjustment_history: List[Dict] = []
    
    def compute_adjustment(
        self,
        current_metrics: PerformanceMetrics,
        target_metrics: Dict,
        compliance_result: Dict
    ) -> Tuple[BatchSizeRecommendation, int]:
        """バッチサイズ調整計算"""
        
        current_batch_size = current_metrics.batch_size
        adjustment = BatchSizeRecommendation.MAINTAIN
        new_batch_size = current_batch_size
        
        # SLA 未達の場合、バッチサイズ削減
        if not compliance_result["is_compliant"]:
            for violation in compliance_result["violations"]:
                if violation["severity"] in ["high", "critical"]:
                    if violation["metric"] in ["p95_latency", "p99_latency"]:
                        adjustment = BatchSizeRecommendation.DECREASE
                        break
        
        # SLA 達成時、スループット向上目指す
        elif compliance_result["compliance_score"] >= 0.95:
            if current_metrics.throughput_req_per_sec < self.config.target_throughput:
                adjustment = BatchSizeRecommendation.INCREASE
        
        # バッチサイズ調整
        if adjustment == BatchSizeRecommendation.INCREASE:
            new_batch_size = min(
                current_batch_size + self.config.adjustment_step,
                self.config.max_batch_size
            )
        elif adjustment == BatchSizeRecommendation.DECREASE:
            new_batch_size = max(
                current_batch_size - self.config.adjustment_step,
                self.config.min_batch_size
            )
        
        # 履歴記録
        self.adjustment_history.append({
            "timestamp": current_metrics.timestamp,
            "current_batch_size": current_batch_size,
            "new_batch_size": new_batch_size,
            "adjustment": adjustment.value,
            "reason": self._get_reason(compliance_result),
        })
        
        return adjustment, new_batch_size
    
    def _get_reason(self, compliance_result: Dict) -> str:
        """調整理由"""
        if not compliance_result["is_compliant"]:
            violations = [v["metric"] for v in compliance_result["violations"]]
            return f"SLA violation: {', '.join(violations)}"
        else:
            return "Optimization for throughput"


# ============================================================================
# Dynamic Batch Optimizer
# ============================================================================

class DynamicBatchOptimizer:
    """動的バッチ最適化エンジン"""
    
    def __init__(self, config: Optional[DynamicBatchConfig] = None):
        self.config = config or DynamicBatchConfig()
        self.current_batch_size = self.config.initial_batch_size
        self.predictor = BatchSizePredictor(self.config)
        self.sla_monitor = SLAComplianceMonitor(self.config.sla_target)
        self.feedback_loop = FeedbackLoop(self.config)
        self.metrics_history: List[PerformanceMetrics] = []
        self.optimization_stats: Dict = {
            "total_optimizations": 0,
            "successful_improvements": 0,
            "sla_violations": 0,
        }
    
    async def optimize_batch_size(
        self,
        current_metrics: PerformanceMetrics
    ) -> Dict:
        """バッチサイズ最適化"""
        
        # 現在のメトリクス記録
        self.metrics_history.append(current_metrics)
        self.predictor.add_observation(current_metrics)
        
        # SLA コンプライアンスチェック
        compliance_result = self.sla_monitor.check_compliance(current_metrics)
        
        if not compliance_result["is_compliant"]:
            self.optimization_stats["sla_violations"] += 1
        
        # バッチサイズ推奨計算
        target_metrics = self._get_target_metrics()
        adjustment, new_batch_size = self.feedback_loop.compute_adjustment(
            current_metrics, target_metrics, compliance_result
        )
        
        # 次のバッチサイズ予測
        predicted = self.predictor.predict_performance(new_batch_size)
        
        # 最適化統計更新
        self.optimization_stats["total_optimizations"] += 1
        if new_batch_size != current_metrics.batch_size:
            self.optimization_stats["successful_improvements"] += 1
        
        await asyncio.sleep(0)  # 非同期化
        
        return {
            "current_batch_size": current_metrics.batch_size,
            "recommended_batch_size": new_batch_size,
            "adjustment": adjustment.value,
            "compliance": compliance_result,
            "predicted_metrics": predicted,
            "sla_compliant": compliance_result["is_compliant"],
        }
    
    def _get_target_metrics(self) -> Dict:
        """目標メトリクス"""
        return {
            "target_latency": self.config.target_latency_ms,
            "target_throughput": self.config.target_throughput,
        }
    
    def get_optimization_report(self) -> Dict:
        """最適化レポート"""
        
        if not self.metrics_history:
            return {"status": "no_data"}
        
        throughputs = [m.throughput_req_per_sec for m in self.metrics_history]
        latencies = [m.avg_latency_ms for m in self.metrics_history]
        efficiencies = [m.efficiency_score for m in self.metrics_history]
        
        return {
            "status": "active",
            "total_observations": len(self.metrics_history),
            "current_batch_size": self.current_batch_size,
            "optimization_stats": self.optimization_stats,
            "sla_compliance": self.sla_monitor.get_compliance_stats(),
            "performance_summary": {
                "avg_throughput": np.mean(throughputs) if throughputs else 0,
                "max_throughput": np.max(throughputs) if throughputs else 0,
                "avg_latency": np.mean(latencies) if latencies else 0,
                "min_latency": np.min(latencies) if latencies else 0,
                "avg_efficiency": np.mean(efficiencies) if efficiencies else 0,
            },
            "adjustment_history": self.feedback_loop.adjustment_history[-10:],
        }


# ============================================================================
# Performance Estimator
# ============================================================================

class PerformanceEstimator:
    """パフォーマンス推定エンジン"""
    
    @staticmethod
    def estimate_throughput(
        batch_size: int,
        inference_time_per_batch_ms: float
    ) -> float:
        """スループット推定 (req/sec)"""
        if inference_time_per_batch_ms == 0:
            return 0.0
        return (batch_size * 1000.0) / inference_time_per_batch_ms
    
    @staticmethod
    def estimate_latency(
        batch_size: int,
        inference_time_per_batch_ms: float,
        queueing_latency_ms: float = 0.0
    ) -> float:
        """レイテンシ推定 (ms)"""
        avg_queuing_per_item = queueing_latency_ms / max(batch_size, 1)
        return inference_time_per_batch_ms + avg_queuing_per_item
    
    @staticmethod
    def estimate_power_consumption(
        batch_size: int,
        base_power_w: float = 250.0,
        gpu_utilization: float = 0.8
    ) -> float:
        """消費電力推定 (W)"""
        # バッチサイズに比例して GPU 使用率が増加
        utilization = min(gpu_utilization * (batch_size / 64.0), 1.0)
        return base_power_w * utilization


# ============================================================================
# Utility Functions
# ============================================================================

async def create_sample_metrics() -> List[PerformanceMetrics]:
    """サンプルメトリクス作成"""
    metrics_list = []
    
    for batch_size in [8, 16, 32, 64, 128]:
        # バッチサイズに応じたシミュレーション
        throughput = 5000 * math.sqrt(batch_size)
        latency = 5 + math.log2(batch_size) * 0.5
        
        metrics = PerformanceMetrics(
            timestamp=float(len(metrics_list)),
            batch_size=batch_size,
            throughput_req_per_sec=throughput,
            avg_latency_ms=latency,
            p95_latency_ms=latency * 1.2,
            p99_latency_ms=latency * 1.5,
            memory_used_mb=100 + batch_size * 10,
            gpu_utilization_percent=min(30 + batch_size * 0.5, 95.0),
            power_consumption_w=200 + batch_size * 1.5,
        )
        metrics_list.append(metrics)
        await asyncio.sleep(0)
    
    return metrics_list


# ============================================================================
# Global Initialization
# ============================================================================

_dynamic_optimizer: Optional[DynamicBatchOptimizer] = None


async def initialize_dynamic_optimizer(
    config: Optional[DynamicBatchConfig] = None
) -> DynamicBatchOptimizer:
    """動的最適化エンジン初期化"""
    global _dynamic_optimizer
    
    _dynamic_optimizer = DynamicBatchOptimizer(config)
    await asyncio.sleep(0)
    
    return _dynamic_optimizer


def get_dynamic_optimizer() -> DynamicBatchOptimizer:
    """動的最適化エンジン取得"""
    if _dynamic_optimizer is None:
        raise RuntimeError("動的最適化エンジンが初期化されていません")
    return _dynamic_optimizer
