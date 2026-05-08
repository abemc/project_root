"""
マイクロサービスシステム テスト

ServiceBase, ServiceRegistry, ServiceCommunication,
ServiceHealth, LoadBalancer の包括的なテスト
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from src.microservices.base_service import (
    ServiceBase, ServiceConfig, ServiceStatus,
    ServiceMetrics, ServiceLogLevel
)
from src.microservices.service_registry import (
    ServiceRegistry, ServiceInstance,
    ServiceRegistrationStatus
)
from src.microservices.service_communication import (
    ServiceRequest, ServiceResponse,
    CircuitBreaker, RetryPolicy,
    HTTPRestChannel, ServiceCommunicationManager
)
from src.microservices.service_health import (
    HealthCheckManager, HealthCheckType,
    HealthStatus, HealthRecoveryManager,
    RecoveryStrategy
)
from src.microservices.load_balancer import (
    LoadBalancingStrategy, LoadBalancerFactory,
    RoundRobinLoadBalancer, LeastConnectionsLoadBalancer
)


# テスト用のモックサービス
class MockService(ServiceBase):
    """テスト用モックサービス"""
    
    async def initialize(self) -> bool:
        return True
    
    async def shutdown(self) -> None:
        pass


class TestServiceBase:
    """ServiceBase テスト"""
    
    def test_service_creation(self):
        """サービス作成テスト"""
        config = ServiceConfig(name="test-service", version="1.0.0")
        service = MockService(config)
        
        assert service.config.name == "test-service"
        assert service.status == ServiceStatus.STARTING
    
    @pytest.mark.asyncio
    async def test_service_startup(self):
        """サービス起動テスト"""
        config = ServiceConfig(name="test-service")
        service = MockService(config)
        
        result = await service.start()
        
        assert result is True
        assert service.status == ServiceStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_service_shutdown(self):
        """サービスシャットダウンテスト"""
        config = ServiceConfig(name="test-service")
        service = MockService(config)
        
        await service.start()
        await service.stop()
        
        assert service.status == ServiceStatus.STOPPED
    
    def test_request_recording(self):
        """リクエスト記録テスト"""
        config = ServiceConfig(name="test-service")
        service = MockService(config)
        
        service.record_request(latency_ms=100, success=True)
        service.record_request(latency_ms=150, success=True)
        service.record_request(latency_ms=200, success=False)
        
        assert service.metrics.total_requests == 3
        assert service.metrics.successful_requests == 2
        assert service.metrics.failed_requests == 1


class TestServiceRegistry:
    """ServiceRegistry テスト"""
    
    def test_register_service(self):
        """サービス登録テスト"""
        registry = ServiceRegistry()
        
        instance = registry.register(
            service_name="api-service",
            host="localhost",
            port=8080
        )
        
        assert instance.service_name == "api-service"
        assert instance.status == ServiceRegistrationStatus.REGISTERED
    
    def test_discover_service(self):
        """サービス発見テスト"""
        registry = ServiceRegistry()
        
        registry.register("api-service", "localhost", 8080)
        registry.register("api-service", "localhost", 8081)
        
        instances = registry.discover("api-service")
        
        assert len(instances) == 2
    
    def test_deregister_service(self):
        """サービス登録解除テスト"""
        registry = ServiceRegistry()
        
        instance = registry.register("api-service", "localhost", 8080)
        result = registry.deregister("api-service", instance.instance_id)
        
        assert result is True
        assert len(registry.discover("api-service")) == 0
    
    def test_heartbeat_update(self):
        """ハートビート更新テスト"""
        registry = ServiceRegistry()
        
        instance = registry.register("api-service", "localhost", 8080)
        initial_heartbeat = instance.last_heartbeat
        
        # 少し待つ
        import time
        time.sleep(0.01)
        
        registry.heartbeat(instance.instance_id)
        
        assert instance.last_heartbeat > initial_heartbeat
    
    def test_instance_alive_check(self):
        """インスタンス有効性チェックテスト"""
        registry = ServiceRegistry()
        
        instance = registry.register("api-service", "localhost", 8080)
        
        # 即座はalive
        assert instance.is_alive() is True
        
        # タイムアウト設定で古くする
        instance.last_heartbeat = datetime.utcnow() - timedelta(seconds=100)
        
        assert instance.is_alive(timeout_seconds=10) is False


class TestServiceCommunication:
    """ServiceCommunication テスト"""
    
    def test_service_request_creation(self):
        """リクエスト作成テスト"""
        request = ServiceRequest(
            service_name="api-service",
            method="POST",
            path="/api/users",
            body={"name": "test"}
        )
        
        assert request.service_name == "api-service"
        assert request.method == "POST"
    
    def test_service_response_success(self):
        """成功レスポンステスト"""
        response = ServiceResponse(
            status_code=200,
            body={"success": True}
        )
        
        assert response.is_success is True
        assert response.is_error is False
    
    def test_service_response_error(self):
        """エラーレスポンステスト"""
        response = ServiceResponse(
            status_code=500,
            body={"error": "Internal Error"}
        )
        
        assert response.is_success is False
        assert response.is_error is True
    
    def test_circuit_breaker_closed(self):
        """サーキットブレーカー閉鎖テスト"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # 成功時は状態を保つ
        breaker.record_success()
        assert breaker.state == "CLOSED"
        assert breaker.is_available() is True
    
    def test_circuit_breaker_open(self):
        """サーキットブレーカーオープンテスト"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # 3回失敗するとOPEN
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.state == "OPEN"
        assert breaker.is_available() is False
    
    def test_retry_policy(self):
        """リトライポリシーテスト"""
        policy = RetryPolicy(max_retries=3)
        
        delay_0 = policy.get_delay_ms(0)
        delay_1 = policy.get_delay_ms(1)
        
        assert delay_1 > delay_0  # 指数バックオフ


class TestServiceHealth:
    """ServiceHealth テスト"""
    
    @pytest.mark.asyncio
    async def test_health_check_manager_creation(self):
        """ヘルスチェックマネージャー作成テスト"""
        manager = HealthCheckManager("test-service")
        
        # カスタムチェックを登録
        async def health_check():
            return True
        
        manager.register_check(HealthCheckType.LIVENESS, health_check)
        
        result = await manager.perform_check(HealthCheckType.LIVENESS)
        
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_health_recovery_manager(self):
        """ヘルス回復マネージャーテスト"""
        manager = HealthRecoveryManager("test-service")
        
        # リカバリー戦略を登録
        strategy = RecoveryStrategy("restart")
        async def restart_action():
            pass
        strategy.add_action(restart_action)
        manager.register_recovery_strategy("default", strategy)
        
        # ヘルスチェック結果
        result = await manager.check_and_recover()
        
        assert result["service_name"] == "test-service"


class TestLoadBalancer:
    """LoadBalancer テスト"""
    
    def test_round_robin_balancer(self):
        """ラウンドロビンロードバランサーテスト"""
        balancer = RoundRobinLoadBalancer()
        
        # モックインスタンスを作成
        instances = []
        for i in range(3):
            instance = ServiceInstance(
                service_name="api",
                instance_id=f"inst-{i}",
                host="localhost",
                port=8080 + i
            )
            instances.append(instance)
        
        # ラウンドロビン選択
        selected1 = balancer.select(instances)
        selected2 = balancer.select(instances)
        selected3 = balancer.select(instances)
        selected4 = balancer.select(instances)
        
        # 異なるインスタンスが選択されることを確認
        assert selected1.instance_id != selected2.instance_id
        assert selected2.instance_id != selected3.instance_id
    
    def test_least_connections_balancer(self):
        """最少接続ロードバランサーテスト"""
        balancer = LeastConnectionsLoadBalancer()
        
        # インスタンスメトリクスを設定
        from src.microservices.load_balancer import InstanceMetrics
        
        balancer.register_instance_metrics("inst-1", weight=1)
        balancer.register_instance_metrics("inst-2", weight=1)
        
        # 接続数を設定
        balancer.metrics["inst-1"].active_connections = 5
        balancer.metrics["inst-2"].active_connections = 2
        
        # inst-2が選択されるはず
        instances = []
        for i in range(2):
            instance = ServiceInstance(
                service_name="api",
                instance_id=f"inst-{i+1}",
                host="localhost",
                port=8080 + i
            )
            instances.append(instance)
        
        selected = balancer.select(instances)
        
        assert selected.instance_id == "inst-2"


class TestIntegration:
    """統合テスト"""
    
    @pytest.mark.asyncio
    async def test_service_registry_with_load_balancer(self):
        """レジストリとロードバランサーの統合テスト"""
        registry = ServiceRegistry()
        balancer = RoundRobinLoadBalancer()
        
        # サービス登録
        inst1 = registry.register("api", "localhost", 8080)
        inst2 = registry.register("api", "localhost", 8081)
        
        # 発見
        instances = registry.discover("api")
        assert len(instances) == 2
        
        # ロードバランシング
        selected = balancer.select(instances)
        assert selected is not None
    
    @pytest.mark.asyncio
    async def test_full_service_workflow(self):
        """全体的なサービスワークフローテスト"""
        # 1. サービス作成・起動
        config = ServiceConfig(name="api-service", version="1.0.0")
        service = MockService(config)
        await service.start()
        
        # 2. レジストリに登録
        registry = ServiceRegistry()
        registry.register("api-service", "localhost", 8080)
        
        # 3. 発見
        instances = registry.discover("api-service")
        assert len(instances) > 0
        
        # 4. ロードバランシング
        balancer = RoundRobinLoadBalancer()
        selected = balancer.select(instances)
        assert selected is not None
        
        # 5. シャットダウン
        await service.stop()
        assert service.status == ServiceStatus.STOPPED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
