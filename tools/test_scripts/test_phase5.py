#!/usr/bin/env python3
"""
Phase 5 Test Suite
デプロイメント、リソース最適化、コスト分析のテスト
"""

import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta

# Import Phase 5 modules
from src.self_improvement.deployment_manager import (
    DeploymentManager,
    DeploymentConfig,
    DeploymentEnvironment,
    DeploymentStatus,
    DeploymentPipeline,
    DeploymentRecovery,
    ArtifactType
)

from src.self_improvement.resource_optimizer import (
    ResourceOptimizer,
    ResourceMetrics,
    OptimizationStrategy,
    TokenOptimizer,
    InferenceOptimizer,
    BatchOptimizer
)

from src.self_improvement.cost_analyzer import (
    CostAnalyzer,
    CostModel,
    BillingRecord,
    BudgetManager,
    CostBreakdown,
    BillingPeriod
)


class TestDeploymentManager(unittest.TestCase):
    """DeploymentManager のテストスイート"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DeploymentManager(logs_dir=os.path.join(self.temp_dir, "deployment"))
        
        # テスト用ファイルを作成
        self.test_model_path = os.path.join(self.temp_dir, "model.pt")
        with open(self.test_model_path, 'w') as f:
            f.write("dummy model content")
        
        self.test_target_path = os.path.join(self.temp_dir, "deployed_model.pt")
    
    def test_deployment_config_creation(self):
        """デプロイメント設定の作成テスト"""
        config = self.manager.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.STAGING,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path,
            enable_validation=True
        )
        
        self.assertIsNotNone(config)
        self.assertEqual(config.version, "1.0.0")
        self.assertEqual(config.environment, DeploymentEnvironment.STAGING)
    
    def test_deployment_pipeline_artifact_preparation(self):
        """デプロイメントパイプラインの成果物準備テスト"""
        config = self.manager.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.STAGING,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path
        )
        
        pipeline = DeploymentPipeline(config)
        artifacts = pipeline.prepare_artifacts(
            self.test_model_path,
            {"version": "1.0.0", "model_type": "test"}
        )
        
        self.assertGreaterEqual(len(artifacts), 2)  # モデル + 設定
        self.assertTrue(any(a.artifact_type == ArtifactType.MODEL_WEIGHTS for a in artifacts))
        self.assertTrue(any(a.artifact_type == ArtifactType.CONFIGURATION for a in artifacts))
    
    def test_artifact_validation(self):
        """成果物バリデーションテスト"""
        config = self.manager.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.STAGING,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path
        )
        
        pipeline = DeploymentPipeline(config)
        artifacts = pipeline.prepare_artifacts(
            self.test_model_path,
            {"version": "1.0.0"}
        )
        
        is_valid, results = pipeline.validate_artifacts()
        self.assertTrue(is_valid)
        self.assertTrue(all(v == "PASSED" for v in results.values()))
    
    def test_deployment_execution(self):
        """デプロイメント実行テスト"""
        config = self.manager.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.PRODUCTION,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path,
            enable_validation=True
        )
        
        success, record = self.manager.execute_deployment(config)
        
        self.assertTrue(success)
        self.assertEqual(record.status, DeploymentStatus.COMPLETED)
        self.assertIsNotNone(record.end_time)
    
    def test_deployment_history(self):
        """デプロイメント履歴テスト"""
        config = self.manager.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.STAGING,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path
        )
        
        # 複数のデプロイメントを実行
        for i in range(3):
            self.manager.execute_deployment(config)
        
        history = self.manager.get_deployment_history(limit=10)
        self.assertGreaterEqual(len(history), 3)
    
    def test_backup_and_recovery(self):
        """バックアップとリカバリテスト"""
        recovery = DeploymentRecovery(backup_dir=os.path.join(self.temp_dir, "backups"))
        
        # バックアップを作成
        backup_path = recovery.create_backup(self.test_model_path, "1.0.0")
        self.assertTrue(os.path.exists(backup_path))
        
        # ターゲットパスに復元
        restore_path = os.path.join(self.temp_dir, "restored_model.pt")
        success = recovery.restore_from_backup(backup_path, restore_path)
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(restore_path))


class TestResourceOptimizer(unittest.TestCase):
    """ResourceOptimizer のテストスイート"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.optimizer = ResourceOptimizer(logs_dir=os.path.join(self.temp_dir, "optimization"))
    
    def test_resource_metrics_recording(self):
        """リソースメトリクスの記録テスト"""
        metrics = ResourceMetrics(
            timestamp=datetime.now().isoformat(),
            total_tokens_used=100000,
            prompt_tokens=50000,
            completion_tokens=50000,
            avg_tokens_per_request=1000,
            inference_time_ms=150.5,
            max_inference_time_ms=200.0,
            min_inference_time_ms=100.0,
            batch_size=32,
            requests_processed=100,
            memory_usage_mb=512.0,
            cache_hit_ratio=0.75,
            estimated_cost=0.15
        )
        
        self.optimizer.record_metrics(metrics)
        
        self.assertEqual(len(self.optimizer.metrics_history), 1)
        self.assertEqual(self.optimizer.metrics_history[0].total_tokens_used, 100000)
    
    def test_token_optimizer_analysis(self):
        """トークン最適化の分析テスト"""
        token_opt = TokenOptimizer()
        
        # メトリクス履歴を生成
        metrics_history = []
        for i in range(5):
            metrics = ResourceMetrics(
                timestamp=datetime.now().isoformat(),
                total_tokens_used=100000 + i * 10000,
                prompt_tokens=50000,
                completion_tokens=50000 + i * 5000,
                avg_tokens_per_request=1000,
                inference_time_ms=150.0 + i * 10,
                max_inference_time_ms=200.0,
                min_inference_time_ms=100.0,
                batch_size=32,
                requests_processed=100,
                memory_usage_mb=512.0,
                cache_hit_ratio=0.75,
                estimated_cost=0.15
            )
            metrics_history.append(metrics)
        
        analysis = token_opt.analyze_token_distribution(metrics_history)
        
        self.assertIn('avg_total_tokens', analysis)
        self.assertIn('prompt_to_completion_ratio', analysis)
        self.assertGreater(analysis['avg_total_tokens'], 0)
    
    def test_optimization_execution(self):
        """最適化実行テスト"""
        # メトリクスを記録
        for i in range(3):
            metrics = ResourceMetrics(
                timestamp=datetime.now().isoformat(),
                total_tokens_used=100000,
                prompt_tokens=50000,
                completion_tokens=50000,
                avg_tokens_per_request=1000,
                inference_time_ms=150.0,
                max_inference_time_ms=200.0,
                min_inference_time_ms=100.0,
                batch_size=32,
                requests_processed=100,
                memory_usage_mb=512.0,
                cache_hit_ratio=0.75,
                estimated_cost=0.15
            )
            self.optimizer.record_metrics(metrics)
        
        # 最適化を実行
        result = self.optimizer.run_optimization(strategy=OptimizationStrategy.BALANCED)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertGreater(result.token_reduction_percent, 0)
        self.assertGreater(len(result.recommendations), 0)
    
    def test_inference_optimizer(self):
        """推論最適化テスト"""
        inf_opt = InferenceOptimizer()
        
        # 推論時間を記録
        for time_ms in [100, 150, 120, 200, 110]:
            inf_opt.record_inference_time(time_ms)
        
        analysis = inf_opt.analyze_inference_performance()
        
        self.assertIn('avg_inference_time_ms', analysis)
        self.assertIn('p95_inference_time_ms', analysis)
        self.assertIn('p99_inference_time_ms', analysis)
        self.assertGreater(analysis['avg_inference_time_ms'], 0)
    
    def test_batch_optimizer(self):
        """バッチ最適化テスト"""
        batch_opt = BatchOptimizer()
        
        # メトリクス履歴を生成
        metrics_history = []
        for batch_size in [16, 32, 64, 32, 16]:
            metrics = ResourceMetrics(
                timestamp=datetime.now().isoformat(),
                total_tokens_used=100000,
                prompt_tokens=50000,
                completion_tokens=50000,
                avg_tokens_per_request=1000,
                inference_time_ms=150.0,
                max_inference_time_ms=200.0,
                min_inference_time_ms=100.0,
                batch_size=batch_size,
                requests_processed=100,
                memory_usage_mb=512.0,
                cache_hit_ratio=0.75,
                estimated_cost=0.15
            )
            metrics_history.append(metrics)
        
        analysis = batch_opt.analyze_batch_efficiency(metrics_history)
        
        self.assertIn('avg_batch_size', analysis)
        self.assertIn('optimal_batch_size', analysis)


class TestCostAnalyzer(unittest.TestCase):
    """CostAnalyzer のテストスイート"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cost_model = CostModel(
            model_id="test_model",
            pricing_per_1k_tokens=0.0015,
            pricing_per_request=0.0001,
            pricing_per_hour_compute=10.0
        )
        self.analyzer = CostAnalyzer(
            cost_model=self.cost_model,
            logs_dir=os.path.join(self.temp_dir, "cost")
        )
    
    def test_cost_model_calculation(self):
        """コストモデルの計算テスト"""
        # トークンコスト
        token_cost = self.cost_model.calculate_token_cost(1000000)  # 1M tokens
        self.assertGreater(token_cost, 0)
        
        # リクエストコスト
        request_cost = self.cost_model.calculate_request_cost(1000)
        self.assertEqual(request_cost, 0.1)  # 1000 * 0.0001
        
        # 総コスト
        total_cost = self.cost_model.calculate_total_cost(
            num_tokens=1000000,
            num_requests=1000
        )
        self.assertGreater(total_cost, 0)
    
    def test_cost_analysis(self):
        """コスト分析テスト"""
        usage_data = {
            'total_tokens': 1000000,
            'total_requests': 5000,
            'total_compute_hours': 10.0
        }
        
        breakdown = self.analyzer.analyze_costs(usage_data, period_days=30)
        
        self.assertIsNotNone(breakdown)
        self.assertGreater(breakdown.total_cost, 0)
        self.assertGreater(breakdown.monthly_projection, 0)
        self.assertGreater(breakdown.yearly_projection, 0)
    
    def test_billing_report_generation(self):
        """請求レポート生成テスト"""
        period_start = datetime.now() - timedelta(days=30)
        period_end = datetime.now()
        
        record = self.analyzer.generate_billing_report(period_start, period_end)
        
        self.assertIsNotNone(record)
        self.assertGreater(record.total_cost, 0)
        self.assertEqual(record.currency, "USD")
    
    def test_budget_management(self):
        """予算管理テスト"""
        budget_mgr = BudgetManager(monthly_budget=1000.0)
        
        # 支出を記録
        budget_mgr.record_spend(300.0)
        budget_mgr.record_spend(200.0)
        
        status = budget_mgr.get_budget_status()
        
        self.assertEqual(status['spent'], 500.0)
        self.assertEqual(status['remaining'], 500.0)
        self.assertEqual(status['percentage_used'], 50.0)
    
    def test_roi_calculation(self):
        """ROI計算テスト"""
        improvement_metrics = {
            'error_reduction_percent': 10,
            'latency_improvement_percent': 20,
            'token_savings_percent': 15
        }
        
        roi = self.analyzer.calculate_roi(
            total_cost=5000,
            improvement_metrics=improvement_metrics
        )
        
        self.assertIn('roi_percent', roi)
        self.assertIn('payback_period_months', roi)
        self.assertGreater(roi['estimated_annual_value'], 0)
    
    def test_cost_summary(self):
        """コストサマリーテスト"""
        # メトリクスを複数記録
        for i in range(3):
            usage_data = {
                'total_tokens': 1000000,
                'total_requests': 5000,
                'total_compute_hours': 10.0
            }
            self.analyzer.analyze_costs(usage_data)
        
        summary = self.analyzer.get_cost_summary()
        
        self.assertIn('current_monthly_cost', summary)
        self.assertIn('budget_status', summary)


class Phase5IntegrationTest(unittest.TestCase):
    """Phase 5 統合テスト"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # テスト用ファイルを作成
        self.test_model_path = os.path.join(self.temp_dir, "model.pt")
        with open(self.test_model_path, 'w') as f:
            f.write("dummy model content")
        
        self.test_target_path = os.path.join(self.temp_dir, "deployed_model.pt")
    
    def test_end_to_end_workflow(self):
        """エンドツーエンドワークフローテスト"""
        
        # 1. デプロイメント
        deployment_mgr = DeploymentManager(
            logs_dir=os.path.join(self.temp_dir, "deployment")
        )
        config = deployment_mgr.create_deployment_config(
            version="1.0.0",
            environment=DeploymentEnvironment.PRODUCTION,
            source_model_path=self.test_model_path,
            target_model_path=self.test_target_path
        )
        success, deploy_record = deployment_mgr.execute_deployment(config)
        self.assertTrue(success)
        
        # 2. リソース最適化
        resource_opt = ResourceOptimizer(
            logs_dir=os.path.join(self.temp_dir, "optimization")
        )
        metrics = ResourceMetrics(
            timestamp=datetime.now().isoformat(),
            total_tokens_used=100000,
            prompt_tokens=50000,
            completion_tokens=50000,
            avg_tokens_per_request=1000,
            inference_time_ms=150.0,
            max_inference_time_ms=200.0,
            min_inference_time_ms=100.0,
            batch_size=32,
            requests_processed=100,
            memory_usage_mb=512.0,
            cache_hit_ratio=0.75,
            estimated_cost=0.15
        )
        resource_opt.record_metrics(metrics)
        
        # 3回記録して最適化を実行
        for i in range(2):
            resource_opt.record_metrics(metrics)
        
        opt_result = resource_opt.run_optimization()
        self.assertIsNotNone(opt_result)
        
        # 3. コスト分析
        cost_analyzer = CostAnalyzer(
            logs_dir=os.path.join(self.temp_dir, "cost")
        )
        usage_data = {
            'total_tokens': 1000000,
            'total_requests': 5000,
            'total_compute_hours': 10.0
        }
        cost_breakdown = cost_analyzer.analyze_costs(usage_data)
        self.assertGreater(cost_breakdown.total_cost, 0)
        
        print("\n✅ Phase 5 End-to-End Integration Test PASSED")


def run_tests():
    """テストを実行"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストスイートを追加
    suite.addTests(loader.loadTestsFromTestCase(TestDeploymentManager))
    suite.addTests(loader.loadTestsFromTestCase(TestResourceOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestCostAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(Phase5IntegrationTest))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # サマリーを出力
    print("\n" + "="*70)
    print("PHASE 5 TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL PHASE 5 TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
