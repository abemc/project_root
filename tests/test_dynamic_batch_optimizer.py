# -*- coding: utf-8 -*-
"""
動的バッチ最適化テスト
Phase 12 Task 3

AI 駆動型バッチサイズ最適化・SLA 対応テスト
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from inference.dynamic_batch_optimizer import (
    OptimizationStrategy,
    BatchSizeRecommendation,
    PerformanceMetrics,
    SLATarget,
    DynamicBatchConfig,
    BatchSizePredictor,
    SLAComplianceMonitor,
    FeedbackLoop,
    DynamicBatchOptimizer,
    PerformanceEstimator,
    create_sample_metrics,
    initialize_dynamic_optimizer,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def performance_metrics():
    """パフォーマンスメトリクス"""
    return PerformanceMetrics(
        timestamp=time.time(),
        batch_size=32,
        throughput_req_per_sec=30000.0,
        avg_latency_ms=5.5,
        p95_latency_ms=8.0,
        p99_latency_ms=12.0,
        memory_used_mb=500.0,
        gpu_utilization_percent=75.0,
        power_consumption_w=300.0,
    )


@pytest.fixture
def sla_target():
    """SLA ターゲット"""
    return SLATarget(
        p95_latency_ms=10.0,
        p99_latency_ms=20.0,
        min_throughput=10000.0,
        max_power_w=350.0,
    )


@pytest.fixture
def dynamic_config(sla_target):
    """動的バッチ設定"""
    return DynamicBatchConfig(
        min_batch_size=1,
        max_batch_size=128,
        initial_batch_size=32,
        sla_target=sla_target,
        optimization_strategy=OptimizationStrategy.SLA_AWARE,
    )


@pytest.fixture
async def sample_metrics():
    """サンプルメトリクス"""
    return await create_sample_metrics()


# ============================================================================
# TestPerformanceMetrics
# ============================================================================

class TestPerformanceMetrics:
    """パフォーマンスメトリクステスト"""
    
    def test_metrics_creation(self, performance_metrics):
        """メトリクス作成"""
        assert performance_metrics.batch_size == 32
        assert performance_metrics.throughput_req_per_sec == 30000.0
        assert performance_metrics.avg_latency_ms == 5.5
    
    def test_efficiency_score_calculation(self, performance_metrics):
        """効率スコア計算"""
        score = performance_metrics.efficiency_score
        assert score > 0
        # 効率スコア = スループット / (レイテンシ / 1000)
        expected = 30000.0 / (5.5 / 1000.0)
        assert abs(score - expected) < 0.1


# ============================================================================
# TestSLATarget
# ============================================================================

class TestSLATarget:
    """SLA ターゲットテスト"""
    
    def test_sla_target_creation(self, sla_target):
        """SLA ターゲット作成"""
        assert sla_target.p95_latency_ms == 10.0
        assert sla_target.p99_latency_ms == 20.0
        assert sla_target.min_throughput == 10000.0
        assert sla_target.max_power_w == 350.0


# ============================================================================
# TestBatchSizePredictor
# ============================================================================

class TestBatchSizePredictor:
    """バッチサイズ予測テスト"""
    
    def test_predictor_creation(self, dynamic_config):
        """予測エンジン作成"""
        predictor = BatchSizePredictor(dynamic_config)
        
        assert len(predictor.history) == 0
        assert len(predictor.predictions) == 0
    
    def test_add_observation(self, dynamic_config, performance_metrics):
        """観測データ追加"""
        predictor = BatchSizePredictor(dynamic_config)
        predictor.add_observation(performance_metrics)
        
        assert len(predictor.history) == 1
    
    def test_predict_performance_no_history(self, dynamic_config):
        """パフォーマンス予測 (履歴なし)"""
        predictor = BatchSizePredictor(dynamic_config)
        prediction = predictor.predict_performance(64)
        
        assert "batch_size" in prediction
        assert "predicted_throughput" in prediction
        assert "predicted_latency" in prediction
        assert prediction["batch_size"] == 64
    
    def test_predict_performance_with_history(self, dynamic_config, sample_metrics):
        """パフォーマンス予測 (履歴あり)"""
        predictor = BatchSizePredictor(dynamic_config)
        
        for metrics in sample_metrics:
            predictor.add_observation(metrics)
        
        prediction = predictor.predict_performance(48)
        
        assert prediction["predicted_throughput"] > 0
        assert prediction["predicted_latency"] > 0
        assert prediction["confidence"] > 0.5


# ============================================================================
# TestSLAComplianceMonitor
# ============================================================================

class TestSLAComplianceMonitor:
    """SLA コンプライアンスモニターテスト"""
    
    def test_monitor_creation(self, sla_target):
        """モニター作成"""
        monitor = SLAComplianceMonitor(sla_target)
        
        assert monitor.sla_target == sla_target
        assert len(monitor.violations) == 0
    
    def test_check_compliance_compliant(self, sla_target):
        """SLA コンプライアンスチェック (準拠)"""
        monitor = SLAComplianceMonitor(sla_target)
        
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            batch_size=32,
            throughput_req_per_sec=30000.0,
            avg_latency_ms=5.0,
            p95_latency_ms=8.0,
            p99_latency_ms=12.0,
            memory_used_mb=500.0,
            gpu_utilization_percent=75.0,
            power_consumption_w=300.0,
        )
        
        result = monitor.check_compliance(metrics)
        
        assert result["is_compliant"] is True
        assert len(result["violations"]) == 0
    
    def test_check_compliance_latency_violation(self, sla_target):
        """SLA コンプライアンスチェック (レイテンシ違反)"""
        monitor = SLAComplianceMonitor(sla_target)
        
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            batch_size=32,
            throughput_req_per_sec=30000.0,
            avg_latency_ms=5.0,
            p95_latency_ms=15.0,  # 違反
            p99_latency_ms=25.0,  # 違反
            memory_used_mb=500.0,
            gpu_utilization_percent=75.0,
            power_consumption_w=300.0,
        )
        
        result = monitor.check_compliance(metrics)
        
        assert result["is_compliant"] is False
        assert len(result["violations"]) >= 2
    
    def test_get_compliance_stats(self, sla_target):
        """コンプライアンス統計"""
        monitor = SLAComplianceMonitor(sla_target)
        
        # 複数の観測を追加
        for i in range(5):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                batch_size=32 + i,
                throughput_req_per_sec=30000.0,
                avg_latency_ms=5.0,
                p95_latency_ms=8.0,
                p99_latency_ms=12.0,
                memory_used_mb=500.0,
                gpu_utilization_percent=75.0,
                power_consumption_w=300.0,
            )
            monitor.check_compliance(metrics)
        
        stats = monitor.get_compliance_stats()
        
        assert "compliant_percent" in stats
        assert stats["compliant_percent"] >= 0


# ============================================================================
# TestFeedbackLoop
# ============================================================================

class TestFeedbackLoop:
    """フィードバックループテスト"""
    
    def test_feedback_loop_creation(self, dynamic_config):
        """フィードバックループ作成"""
        loop = FeedbackLoop(dynamic_config)
        
        assert len(loop.adjustment_history) == 0
    
    def test_compute_adjustment_maintain(self, dynamic_config, performance_metrics):
        """調整計算 (維持)"""
        loop = FeedbackLoop(dynamic_config)
        
        compliance_result = {
            "is_compliant": True,
            "compliance_score": 0.9,
            "violations": [],
        }
        
        adjustment, new_batch_size = loop.compute_adjustment(
            performance_metrics,
            {"target_latency": 10.0, "target_throughput": 50000.0},
            compliance_result
        )
        
        # 完全準拠時は、スループット目標未達でない場合は維持
        if performance_metrics.throughput_req_per_sec >= 50000.0:
            assert adjustment == BatchSizeRecommendation.MAINTAIN
    
    def test_compute_adjustment_decrease(self, dynamic_config, performance_metrics):
        """調整計算 (削減)"""
        loop = FeedbackLoop(dynamic_config)
        
        # SLA 違反の場合
        compliance_result = {
            "is_compliant": False,
            "compliance_score": 0.5,
            "violations": [
                {
                    "metric": "p95_latency",
                    "severity": "high",
                    "target": 10.0,
                    "actual": 15.0,
                }
            ],
        }
        
        adjustment, new_batch_size = loop.compute_adjustment(
            performance_metrics,
            {"target_latency": 10.0},
            compliance_result
        )
        
        assert adjustment == BatchSizeRecommendation.DECREASE
        assert new_batch_size < performance_metrics.batch_size


# ============================================================================
# TestDynamicBatchOptimizer
# ============================================================================

class TestDynamicBatchOptimizer:
    """動的バッチ最適化テスト"""
    
    def test_optimizer_creation(self, dynamic_config):
        """最適化エンジン作成"""
        optimizer = DynamicBatchOptimizer(dynamic_config)
        
        assert optimizer.current_batch_size == dynamic_config.initial_batch_size
        assert len(optimizer.metrics_history) == 0
    
    @pytest.mark.asyncio
    async def test_optimize_batch_size(self, dynamic_config, performance_metrics):
        """バッチサイズ最適化"""
        optimizer = DynamicBatchOptimizer(dynamic_config)
        
        result = await optimizer.optimize_batch_size(performance_metrics)
        
        assert "current_batch_size" in result
        assert "recommended_batch_size" in result
        assert "compliance" in result
        assert "predicted_metrics" in result
    
    @pytest.mark.asyncio
    async def test_optimize_with_multiple_metrics(
        self, dynamic_config, sample_metrics
    ):
        """複数メトリクスでの最適化"""
        optimizer = DynamicBatchOptimizer(dynamic_config)
        
        results = []
        for metrics in sample_metrics:
            result = await optimizer.optimize_batch_size(metrics)
            results.append(result)
        
        assert len(results) == len(sample_metrics)
        assert len(optimizer.metrics_history) == len(sample_metrics)
    
    def test_get_optimization_report(self, dynamic_config, sample_metrics):
        """最適化レポート"""
        optimizer = DynamicBatchOptimizer(dynamic_config)
        
        # メトリクス追加
        for metrics in sample_metrics:
            optimizer.metrics_history.append(metrics)
            optimizer.predictor.add_observation(metrics)
        
        report = optimizer.get_optimization_report()
        
        assert "status" in report
        assert "optimization_stats" in report
        assert "performance_summary" in report


# ============================================================================
# TestPerformanceEstimator
# ============================================================================

class TestPerformanceEstimator:
    """パフォーマンス推定テスト"""
    
    def test_estimate_throughput(self):
        """スループット推定"""
        throughput = PerformanceEstimator.estimate_throughput(
            batch_size=32,
            inference_time_per_batch_ms=10.0
        )
        
        # スループット = (バッチサイズ * 1000) / 推論時間
        expected = (32 * 1000.0) / 10.0
        assert abs(throughput - expected) < 0.1
    
    def test_estimate_latency(self):
        """レイテンシ推定"""
        latency = PerformanceEstimator.estimate_latency(
            batch_size=32,
            inference_time_per_batch_ms=10.0,
            queueing_latency_ms=1.0
        )
        
        # バッチあたりの平均キューイング = 1.0 / 32
        expected = 10.0 + (1.0 / 32.0)
        assert abs(latency - expected) < 0.1
    
    def test_estimate_power_consumption(self):
        """消費電力推定"""
        power = PerformanceEstimator.estimate_power_consumption(
            batch_size=32,
            base_power_w=250.0,
            gpu_utilization=0.8
        )
        
        assert power > 0
        assert power <= 250.0


# ============================================================================
# TestIntegration
# ============================================================================

class TestIntegration:
    """統合テスト"""
    
    @pytest.mark.asyncio
    async def test_full_optimization_flow(self):
        """完全な最適化フロー"""
        config = DynamicBatchConfig(
            optimization_strategy=OptimizationStrategy.SLA_AWARE,
        )
        
        optimizer = await initialize_dynamic_optimizer(config)
        metrics_list = await create_sample_metrics()
        
        for metrics in metrics_list:
            result = await optimizer.optimize_batch_size(metrics)
            assert "recommended_batch_size" in result
        
        report = optimizer.get_optimization_report()
        assert report["status"] == "active"


# ============================================================================
# Test実行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
