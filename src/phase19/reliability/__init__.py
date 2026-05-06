"""
Phase 19 Reliability & SLA Implementation

エンタープライズ本番化フェーズ - Task 1実装

実装モジュール:
- circuit_breaker: 状態遷移・自動リカバリー
- retry_manager: 複数のバックオフ戦略
- failover_strategy: Primary/Backup管理
- sla_monitor: 99.99% SLA監視
- health_check: 定期的なヘルスチェック
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerMetrics,
    CircuitBreakerRegistry,
    register_circuit_breaker,
    get_circuit_breaker,
)

from .retry_manager import (
    RetryManager,
    RetryConfig,
    BackoffStrategy,
    RetryMetrics,
    retry,
)

from .failover_strategy import (
    FailoverStrategy,
    FailoverConfig,
    ServiceEndpoint,
    FailoverMetrics,
)

from .sla_monitor import (
    SLAMonitor,
    SLAThresholds,
    SLAMetrics,
    SLABreach,
)

from .health_check import (
    HealthChecker,
    HealthCheckConfig,
    HealthCheckResult,
    HealthCheckRegistry,
    register_health_check,
    get_health_check,
    start_all_health_checks,
    stop_all_health_checks,
    get_all_health_status,
)

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitBreakerMetrics",
    "CircuitBreakerRegistry",
    "register_circuit_breaker",
    "get_circuit_breaker",
    
    # Retry Manager
    "RetryManager",
    "RetryConfig",
    "BackoffStrategy",
    "RetryMetrics",
    "retry",
    
    # Failover Strategy
    "FailoverStrategy",
    "FailoverConfig",
    "ServiceEndpoint",
    "FailoverMetrics",
    
    # SLA Monitor
    "SLAMonitor",
    "SLAThresholds",
    "SLAMetrics",
    "SLABreach",
    
    # Health Check
    "HealthChecker",
    "HealthCheckConfig",
    "HealthCheckResult",
    "HealthCheckRegistry",
    "register_health_check",
    "get_health_check",
    "start_all_health_checks",
    "stop_all_health_checks",
    "get_all_health_status",
]
