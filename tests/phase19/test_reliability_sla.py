"""
Phase 19 Task 1 - Reliability & SLA Tests

テスト体系: 25個テスト予定
- Circuit Breaker: 8テスト
- Retry Manager: 6テスト
- Failover Strategy: 7テスト
- SLA Monitor: 4テスト

実装状況: フェーズ1（基本構造テスト）
"""

import pytest
import asyncio
from datetime import datetime, timedelta

# Import reliability modules
from src.phase19.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    register_circuit_breaker,
    get_circuit_breaker,
)
from src.phase19.reliability.retry_manager import (
    RetryManager,
    RetryConfig,
    BackoffStrategy,
)
from src.phase19.reliability.failover_strategy import (
    FailoverStrategy,
    FailoverConfig,
    ServiceEndpoint,
)
from src.phase19.reliability.sla_monitor import (
    SLAMonitor,
    SLAThresholds,
)
from src.phase19.reliability.health_check import (
    HealthChecker,
    HealthCheckConfig,
    HealthCheckRegistry,
    register_health_check,
    get_health_check,
)


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_basic_flow():
    """Circuit Breaker: 基本フロー（成功 → 失敗 → OPEN）"""
    config = CircuitBreakerConfig(
        name="test_breaker",
        failure_threshold=2,
        success_threshold=1,
        timeout=1
    )
    breaker = CircuitBreaker(config)
    
    # 成功時
    async def success_func():
        return "success"
    
    result = await breaker.call(success_func)
    assert result == "success"
    assert breaker.get_state() == CircuitState.CLOSED
    
    # 失敗時
    async def failure_func():
        raise Exception("failure")
    
    # 1回目の失敗
    with pytest.raises(Exception):
        await breaker.call(failure_func)
    
    # 2回目の失敗でOPEN
    with pytest.raises(Exception):
        await breaker.call(failure_func)
    
    assert breaker.get_state() == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_metrics():
    """Circuit Breaker: メトリクス収集"""
    config = CircuitBreakerConfig(
        name="test_metrics",
        failure_threshold=5,
        timeout=1
    )
    breaker = CircuitBreaker(config)
    
    async def success_func():
        return "ok"
    
    # 複数回成功
    for _ in range(3):
        await breaker.call(success_func)
    
    metrics = breaker.get_metrics()
    assert metrics.total_calls == 3
    assert metrics.successful_calls == 3
    assert metrics.failed_calls == 0
    assert metrics.get_success_rate() == 100.0


@pytest.mark.asyncio
async def test_circuit_breaker_registry():
    """Circuit Breaker: グローバルレジストリ"""
    config = CircuitBreakerConfig(name="registry_test")
    breaker = CircuitBreaker(config)
    
    register_circuit_breaker("test_service", breaker)
    retrieved = get_circuit_breaker("test_service")
    
    assert retrieved is not None
    assert retrieved.config.name == "registry_test"


# ============================================================================
# Retry Manager Tests
# ============================================================================

@pytest.mark.asyncio
async def test_retry_manager_exponential_backoff():
    """Retry Manager: 指数バックオフ戦略"""
    config = RetryConfig(
        max_retries=3,
        initial_delay=0.1,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        jitter=False
    )
    manager = RetryManager(config)
    
    call_count = 0
    
    async def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return "success"
    
    result = await manager.execute(failing_func)
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_manager_fatal_exception():
    """Retry Manager: 致命的例外は即座に失敗"""
    config = RetryConfig(
        max_retries=3,
        fatal_exceptions=(ValueError,)
    )
    manager = RetryManager(config)
    
    call_count = 0
    
    async def fatal_error_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("fatal error")
    
    with pytest.raises(ValueError):
        await manager.execute(fatal_error_func)
    
    # 1回だけ呼ばれて即座に失敗
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_manager_metrics():
    """Retry Manager: メトリクス"""
    config = RetryConfig(max_retries=2)
    manager = RetryManager(config)
    
    call_count = 0
    
    async def func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("retry")
        return "ok"
    
    await manager.execute(func)
    
    metrics = manager.get_metrics()
    assert metrics.total_attempts == 2
    assert metrics.successful_attempts == 1
    assert metrics.total_retries == 1


# ============================================================================
# Failover Strategy Tests
# ============================================================================

@pytest.mark.asyncio
async def test_failover_strategy_basic():
    """Failover Strategy: 基本フェイルオーバー"""
    primary = ServiceEndpoint(
        name="primary",
        url="http://primary:8000",
        is_primary=True
    )
    backup = ServiceEndpoint(
        name="backup",
        url="http://backup:8000",
        is_primary=False
    )
    
    config = FailoverConfig(primary=primary, backups=[backup])
    strategy = FailoverStrategy(config)
    
    call_sequence = []
    
    async def service_func(**kwargs):
        endpoint = kwargs.get("endpoint")
        call_sequence.append(endpoint.name)
        
        # プライマリは失敗、バックアップは成功
        if endpoint.name == "primary":
            raise Exception("primary failed")
        return "backup success"
    
    result = await strategy.execute(service_func)
    assert result == "backup success"
    assert call_sequence == ["primary", "backup"]


@pytest.mark.asyncio
async def test_failover_strategy_metrics():
    """Failover Strategy: メトリクス"""
    primary = ServiceEndpoint(
        name="primary",
        url="http://primary:8000",
        is_primary=True
    )
    
    config = FailoverConfig(primary=primary, backups=[])
    strategy = FailoverStrategy(config)
    
    async def service_func(**kwargs):
        return "success"
    
    for _ in range(5):
        await strategy.execute(service_func)
    
    metrics = strategy.get_metrics()
    assert metrics.total_requests == 5
    assert metrics.successful_requests == 5
    assert metrics.failover_count == 0


@pytest.mark.asyncio
async def test_failover_strategy_endpoint_status():
    """Failover Strategy: エンドポイントステータス"""
    primary = ServiceEndpoint(
        name="primary",
        url="http://primary:8000"
    )
    
    config = FailoverConfig(primary=primary)
    strategy = FailoverStrategy(config)
    
    status = strategy.get_endpoint_status()
    assert "primary" in status
    assert status["primary"]["is_healthy"] is True
    assert status["primary"]["consecutive_failures"] == 0


# ============================================================================
# SLA Monitor Tests
# ============================================================================

@pytest.mark.asyncio
async def test_sla_monitor_availability():
    """SLA Monitor: 可用性監視"""
    thresholds = SLAThresholds(availability_target=0.95)
    monitor = SLAMonitor(thresholds)
    
    # 95%の可用性を達成
    for i in range(100):
        success = i < 95
        await monitor.record_request(success, 100.0)
    
    report = monitor.get_sla_report()
    assert report["availability"]["actual"] >= 0.95


@pytest.mark.asyncio
async def test_sla_monitor_latency():
    """SLA Monitor: レイテンシ監視"""
    thresholds = SLAThresholds(p99_latency=200.0)
    monitor = SLAMonitor(thresholds)
    
    # P99レイテンシが180msのデータを記録
    for i in range(100):
        latency = 180.0 if i < 99 else 190.0
        await monitor.record_request(True, latency)
    
    report = monitor.get_sla_report()
    assert report["latency"]["p99"]["status"] == "OK"


@pytest.mark.asyncio
async def test_sla_monitor_error_rate():
    """SLA Monitor: エラー率監視"""
    thresholds = SLAThresholds(error_rate_threshold=0.01)
    monitor = SLAMonitor(thresholds)
    
    # 1%未満のエラー率
    for i in range(1000):
        success = i >= 5
        await monitor.record_request(success, 100.0)
    
    report = monitor.get_sla_report()
    assert report["error_rate"]["status"] == "OK"


@pytest.mark.asyncio
async def test_sla_monitor_alert_callback():
    """SLA Monitor: アラートコールバック"""
    alerts_received = []
    
    async def alert_handler(breach):
        alerts_received.append(breach)
    
    thresholds = SLAThresholds(availability_target=0.99)
    monitor = SLAMonitor(thresholds)
    monitor.register_alert_callback(alert_handler)
    
    # 可用性が99%未満になる
    for i in range(100):
        success = i < 90
        await monitor.record_request(success, 100.0)
    
    assert len(alerts_received) > 0


# ============================================================================
# Health Check Tests
# ============================================================================

@pytest.mark.asyncio
async def test_health_checker_success():
    """Health Check: チェック成功"""
    config = HealthCheckConfig(interval=1)
    
    async def check_func():
        return "healthy"
    
    checker = HealthChecker("test_service", check_func, config)
    
    result = await checker.check()
    assert result.is_healthy is True
    assert result.service_name == "test_service"


@pytest.mark.asyncio
async def test_health_checker_failure():
    """Health Check: チェック失敗"""
    config = HealthCheckConfig(interval=1, unhealthy_threshold=1)
    
    async def check_func():
        raise Exception("health check failed")
    
    checker = HealthChecker("test_service", check_func, config)
    
    result = await checker.check()
    assert result.is_healthy is False
    assert result.error_message == "health check failed"


@pytest.mark.asyncio
async def test_health_check_registry():
    """Health Check: レジストリ管理"""
    registry = HealthCheckRegistry()
    
    async def check_func():
        return "ok"
    
    checker = await registry.register("service1", check_func)
    assert checker is not None
    
    retrieved = await registry.get("service1")
    assert retrieved is not None
    assert retrieved.service_name == "service1"


@pytest.mark.asyncio
async def test_health_check_global_registry():
    """Health Check: グローバルレジストリ"""
    async def check_func():
        return "ok"
    
    checker = await register_health_check("test_service", check_func)
    assert checker is not None
    
    retrieved = await get_health_check("test_service")
    assert retrieved is not None


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_with_retry_manager():
    """統合: Circuit Breaker + Retry Manager"""
    from src.phase19.reliability.retry_manager import retry
    
    config = CircuitBreakerConfig(
        name="integration_test",
        failure_threshold=3
    )
    breaker = CircuitBreaker(config)
    
    call_count = 0
    
    @retry(max_retries=2)
    async def service_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("temporary")
        return "success"
    
    result = await breaker.call(service_call)
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_failover_with_sla_monitor():
    """統合: Failover + SLA Monitor"""
    primary = ServiceEndpoint(
        name="primary",
        url="http://primary:8000"
    )
    
    config = FailoverConfig(primary=primary)
    strategy = FailoverStrategy(config)
    
    monitor = SLAMonitor()
    
    async def service_func(**kwargs):
        return "success"
    
    # リクエストとモニタリング
    for i in range(50):
        result = await strategy.execute(service_func)
        await monitor.record_request(result is not None, 100.0)
    
    report = monitor.get_sla_report()
    assert report["availability"]["actual"] == 1.0


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
