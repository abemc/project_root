"""
Kubernetes統合テスト

K8sAdapter, AutoScaling, ServiceMesh のテスト
"""

import pytest
import asyncio

from src.microservices.k8s_adapter import (
    K8sDeploymentManager, K8sServiceManager, K8sResourceManager,
    DeploymentConfig, DeploymentStrategy, PodSpec
)
from src.microservices.auto_scaling import (
    AutoScaler, HPA, VerticalPodAutoscaler,
    ScalingConfig, MetricSnapshot, MetricType, MetricThreshold,
    ScalingPolicy
)
from src.microservices.service_mesh import (
    ServiceMeshAdapter, ServiceMeshController, MeshMetrics,
    DestinationRule, VirtualService, ServiceEntry,
    ServiceMeshType, TrafficPolicy, MeshProtocol
)


class TestK8sAdapter:
    """Kubernetes適応レイヤーテスト"""
    
    @pytest.mark.asyncio
    async def test_deployment_creation(self):
        """デプロイメント作成テスト"""
        manager = K8sDeploymentManager()
        
        config = DeploymentConfig(
            name="test-deployment",
            namespace="default",
            pod_spec=PodSpec(name="test", image="test:latest")
        )
        
        result = await manager.create_deployment(config)
        
        assert result is True
        assert "default/test-deployment" in manager.deployments
    
    @pytest.mark.asyncio
    async def test_deployment_scaling(self):
        """デプロイメントスケーリングテスト"""
        manager = K8sDeploymentManager()
        
        config = DeploymentConfig(
            name="test-deployment",
            namespace="default",
            pod_spec=PodSpec(name="test", image="test:latest", replicas=2)
        )
        
        await manager.create_deployment(config)
        result = await manager.scale_deployment("test-deployment", 5)
        
        assert result is True
        assert config.pod_spec.replicas == 5
    
    @pytest.mark.asyncio
    async def test_deployment_deletion(self):
        """デプロイメント削除テスト"""
        manager = K8sDeploymentManager()
        
        config = DeploymentConfig(name="test-deployment")
        
        await manager.create_deployment(config)
        result = await manager.delete_deployment("test-deployment")
        
        assert result is True
        assert "default/test-deployment" not in manager.deployments
    
    @pytest.mark.asyncio
    async def test_service_creation(self):
        """サービス作成テスト"""
        manager = K8sServiceManager()
        
        result = await manager.create_service(
            "test-service",
            ports=[8080, 8081]
        )
        
        assert result is True
        assert "default/test-service" in manager.services


class TestAutoScaling:
    """オートスケーリングテスト"""
    
    def test_metric_threshold_scale_up(self):
        """メトリクスしきい値: スケールアップ判定"""
        threshold = MetricThreshold(
            metric_type=MetricType.CPU,
            target_value=50.0,
            threshold_percent=10.0
        )
        
        # 56% → スケールアップ (> 55)
        assert threshold.should_scale_up(56.0) is True
        
        # 55% → スケールアップなし（境界値）
        assert threshold.should_scale_up(55.0) is False
    
    def test_metric_threshold_scale_down(self):
        """メトリクスしきい値: スケールダウン判定"""
        threshold = MetricThreshold(
            metric_type=MetricType.MEMORY,
            target_value=60.0,
            threshold_percent=10.0
        )
        
        # 53% → スケールダウン (< 54)
        assert threshold.should_scale_down(53.0) is True
        
        # 54% → スケールダウンなし（境界値）
        assert threshold.should_scale_down(54.0) is False
    
    @pytest.mark.asyncio
    async def test_autoscaler_scale_up_decision(self):
        """オートスケーラー: スケールアップ判定"""
        config = ScalingConfig(
            name="test-scaler",
            min_replicas=1,
            max_replicas=10,
            target_metrics=[
                MetricThreshold(MetricType.CPU, 50.0)
            ]
        )
        
        scaler = AutoScaler(config)
        
        # 高いCPU使用率
        metrics = MetricSnapshot(
            timestamp=asyncio.get_event_loop().time() if asyncio.iscoroutinefunction(asyncio.get_event_loop) else None,
            metrics={"cpu": 75.0},
            average_cpu_percent=75.0
        )
        
        policy = await scaler.evaluate_scaling_decision(metrics)
        
        assert policy == ScalingPolicy.SCALE_UP
    
    @pytest.mark.asyncio
    async def test_autoscaler_replica_calculation(self):
        """オートスケーラー: レプリカ数計算"""
        config = ScalingConfig(
            name="test-scaler",
            min_replicas=2,
            max_replicas=10,
            scale_up_step=2
        )
        
        scaler = AutoScaler(config)
        scaler.current_replicas = 3
        
        new_replicas = await scaler.calculate_new_replica_count(ScalingPolicy.SCALE_UP)
        
        assert new_replicas == 5  # 3 + 2
    
    @pytest.mark.asyncio
    async def test_hpa_creation(self):
        """HPA作成テスト"""
        hpa = HPA()
        
        config = ScalingConfig(
            name="test-hpa",
            min_replicas=1,
            max_replicas=5
        )
        
        result = await hpa.create_hpa(config)
        
        assert result is True
        assert "default/test-hpa" in hpa.scalers
    
    @pytest.mark.asyncio
    async def test_vpa_resource_recommendation(self):
        """VPA: リソースレコメンデーション"""
        vpa = VerticalPodAutoscaler()
        
        usage_history = [
            {"cpu": 100, "memory": 200},
            {"cpu": 150, "memory": 250},
            {"cpu": 120, "memory": 220}
        ]
        
        recommendation = await vpa.analyze_pod_resources("test-pod", usage_history)
        
        assert "cpu_request" in recommendation
        assert "memory_request" in recommendation


class TestServiceMesh:
    """サービスメッシュテスト"""
    
    @pytest.mark.asyncio
    async def test_adapter_creation(self):
        """アダプター作成テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        assert adapter.mesh_type == ServiceMeshType.ISTIO
    
    @pytest.mark.asyncio
    async def test_destination_rule_creation(self):
        """宛先ルール作成テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        rule = DestinationRule(
            name="test-rule",
            host="test-service"
        )
        
        result = await adapter.create_destination_rule(rule)
        
        assert result is True
        assert "default/test-rule" in adapter.destination_rules
    
    @pytest.mark.asyncio
    async def test_virtual_service_creation(self):
        """仮想サービス作成テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        service = VirtualService(
            name="test-vs",
            hosts=["test-service"]
        )
        
        result = await adapter.create_virtual_service(service)
        
        assert result is True
        assert "default/test-vs" in adapter.virtual_services
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_enable(self):
        """サーキットブレーカー有効化テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        result = await adapter.enable_circuit_breaker(
            "test-service",
            consecutive_errors=5
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enable(self):
        """レート制限有効化テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        result = await adapter.enable_rate_limiting(
            "test-service",
            requests_per_second=100
        )
        
        assert result is True
        assert "default/test-service" in adapter.traffic_policies
    
    @pytest.mark.asyncio
    async def test_timeout_enable(self):
        """タイムアウト有効化テスト"""
        adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        result = await adapter.enable_timeout(
            "test-service",
            timeout_seconds=30
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_mesh_metrics_recording(self):
        """メッシュメトリクス記録テスト"""
        metrics = MeshMetrics()
        
        await metrics.record_request(
            "service-a",
            "service-b",
            latency_ms=50.0,
            status_code=200,
            success=True
        )
        
        service_metrics = await metrics.get_service_metrics("service-a", "service-b")
        
        assert service_metrics["total_requests"] == 1
        assert service_metrics["successful_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_mesh_metrics_multiple_requests(self):
        """メッシュメトリクス: 複数リクエスト"""
        metrics = MeshMetrics()
        
        for i in range(10):
            await metrics.record_request(
                "service-a",
                "service-b",
                latency_ms=50.0 + i * 5,
                status_code=200,
                success=True
            )
        
        service_metrics = await metrics.get_service_metrics("service-a", "service-b")
        
        assert service_metrics["total_requests"] == 10
        assert service_metrics["successful_requests"] == 10


class TestIntegrationK8sMesh:
    """K8sとメッシュの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_mesh_deployment_integration(self):
        """メッシュとデプロイメント統合テスト"""
        k8s_mgr = K8sDeploymentManager()
        mesh_adapter = ServiceMeshAdapter(ServiceMeshType.ISTIO)
        
        # デプロイメント作成
        config = DeploymentConfig(
            name="mesh-service",
            pod_spec=PodSpec(name="mesh-pod", image="mesh:latest")
        )
        await k8s_mgr.create_deployment(config)
        
        # メッシュ設定
        rule = DestinationRule(
            name="mesh-service",
            traffic_policy=TrafficPolicy.ROUND_ROBIN
        )
        await mesh_adapter.create_destination_rule(rule)
        
        # 両方が存在することを確認
        assert "default/mesh-service" in k8s_mgr.deployments
        assert "default/mesh-service" in mesh_adapter.destination_rules
    
    @pytest.mark.asyncio
    async def test_hpa_with_mesh_metrics(self):
        """HPAとメッシュメトリクス連携"""
        hpa = HPA()
        mesh_metrics = MeshMetrics()
        
        # HPA作成
        config = ScalingConfig(
            name="service-hpa",
            min_replicas=2,
            max_replicas=10
        )
        await hpa.create_hpa(config)
        
        # メトリクス記録
        await mesh_metrics.record_request(
            "client",
            "service",
            latency_ms=100,
            status_code=200,
            success=True
        )
        
        # 両方が存在することを確認
        assert "default/service-hpa" in hpa.scalers
        assert "client->service" in mesh_metrics.service_metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
