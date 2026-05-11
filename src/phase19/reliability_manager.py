"""
Phase 19 Task 1 - Reliability & SLA Management

統合管理スクリプト

実装完了:
- Circuit Breaker (325行): 状態遷移・メトリクス管理
- Retry Manager (265行): 4つのバックオフ戦略
- Failover Strategy (350行): Primary/Backup管理
- SLA Monitor (300行): 99.99% SLA監視
- Health Check (300行): 定期的なヘルスチェック
- Tests (400行): 31個テスト

合計: 1,940行コード + 31テスト
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.phase19.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    register_circuit_breaker,
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
    HealthCheckRegistry,
    HealthCheckConfig,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReliabilityManager:
    """
    信頼性管理システム
    
    99.99% SLA達成のための統合管理
    """
    
    def __init__(self):
        """初期化"""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_managers: Dict[str, RetryManager] = {}
        self.failover_strategies: Dict[str, FailoverStrategy] = {}
        self.sla_monitors: Dict[str, SLAMonitor] = {}
        self.health_check_registry = HealthCheckRegistry()
        
        logger.info("ReliabilityManager initialized")
    
    # ========================================================================
    # Circuit Breaker Management
    # ========================================================================
    
    def create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60
    ) -> CircuitBreaker:
        """Circuit Breaker を作成"""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout
        )
        breaker = CircuitBreaker(config)
        self.circuit_breakers[name] = breaker
        
        register_circuit_breaker(name, breaker)
        logger.info(f"Created Circuit Breaker: {name}")
        return breaker
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Circuit Breaker を取得"""
        return self.circuit_breakers.get(name)
    
    # ========================================================================
    # Retry Manager Management
    # ========================================================================
    
    def create_retry_manager(
        self,
        name: str,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_strategy: str = "exponential"
    ) -> RetryManager:
        """Retry Manager を作成"""
        strategy_map = {
            "fixed": BackoffStrategy.FIXED,
            "linear": BackoffStrategy.LINEAR,
            "exponential": BackoffStrategy.EXPONENTIAL,
            "random": BackoffStrategy.RANDOM,
        }
        
        config = RetryConfig(
            max_retries=max_retries,
            initial_delay=initial_delay,
            backoff_strategy=strategy_map.get(backoff_strategy, BackoffStrategy.EXPONENTIAL)
        )
        manager = RetryManager(config)
        self.retry_managers[name] = manager
        
        logger.info(f"Created Retry Manager: {name} (strategy={backoff_strategy})")
        return manager
    
    def get_retry_manager(self, name: str) -> Optional[RetryManager]:
        """Retry Manager を取得"""
        return self.retry_managers.get(name)
    
    # ========================================================================
    # Failover Strategy Management
    # ========================================================================
    
    def create_failover_strategy(
        self,
        name: str,
        primary_url: str,
        backup_urls: Optional[List[str]] = None
    ) -> FailoverStrategy:
        """Failover Strategy を作成"""
        primary = ServiceEndpoint(
            name=f"{name}_primary",
            url=primary_url,
            is_primary=True
        )
        
        backups = []
        if backup_urls:
            for i, url in enumerate(backup_urls):
                backup = ServiceEndpoint(
                    name=f"{name}_backup_{i}",
                    url=url,
                    is_primary=False,
                    priority=i
                )
                backups.append(backup)
        
        config = FailoverConfig(primary=primary, backups=backups)
        strategy = FailoverStrategy(config)
        self.failover_strategies[name] = strategy
        
        logger.info(f"Created Failover Strategy: {name} (backups={len(backups)})")
        return strategy
    
    def get_failover_strategy(self, name: str) -> Optional[FailoverStrategy]:
        """Failover Strategy を取得"""
        return self.failover_strategies.get(name)
    
    # ========================================================================
    # SLA Monitor Management
    # ========================================================================
    
    def create_sla_monitor(
        self,
        name: str,
        availability_target: float = 0.9999,
        p99_latency: float = 250.0,
        error_rate_threshold: float = 0.01
    ) -> SLAMonitor:
        """SLA Monitor を作成"""
        thresholds = SLAThresholds(
            availability_target=availability_target,
            p99_latency=p99_latency,
            error_rate_threshold=error_rate_threshold
        )
        monitor = SLAMonitor(thresholds)
        self.sla_monitors[name] = monitor
        
        logger.info(f"Created SLA Monitor: {name} (target={availability_target*100:.2f}%)")
        return monitor
    
    def get_sla_monitor(self, name: str) -> Optional[SLAMonitor]:
        """SLA Monitor を取得"""
        return self.sla_monitors.get(name)
    
    # ========================================================================
    # Health Check Management
    # ========================================================================
    
    async def register_health_check(
        self,
        service_name: str,
        check_func,
        interval: int = 10,
        unhealthy_threshold: int = 3
    ):
        """ヘルスチェッカーを登録"""
        config = HealthCheckConfig(
            interval=interval,
            unhealthy_threshold=unhealthy_threshold
        )
        
        checker = await self.health_check_registry.register(
            service_name,
            check_func,
            config
        )
        
        logger.info(f"Registered health check: {service_name}")
        return checker
    
    async def start_all_health_checks(self) -> None:
        """全ヘルスチェックを開始"""
        await self.health_check_registry.start_all()
        logger.info("Started all health checks")
    
    async def stop_all_health_checks(self) -> None:
        """全ヘルスチェックを停止"""
        await self.health_check_registry.stop_all()
        logger.info("Stopped all health checks")
    
    # ========================================================================
    # Status and Reporting
    # ========================================================================
    
    def get_system_status(self) -> Dict[str, Any]:
        """システム全体のステータスを取得"""
        return {
            "timestamp": datetime.now().isoformat(),
            "circuit_breakers": {
                name: breaker.get_metrics().to_dict()
                for name, breaker in self.circuit_breakers.items()
            },
            "retry_managers": {
                name: manager.get_metrics().to_dict()
                for name, manager in self.retry_managers.items()
            },
            "failover_strategies": {
                name: strategy.get_metrics().__dict__
                for name, strategy in self.failover_strategies.items()
            },
            "sla_monitors": {
                name: monitor.get_sla_report()
                for name, monitor in self.sla_monitors.items()
            },
        }
    
    async def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """ヘルスチェックステータスを取得"""
        return await self.health_check_registry.get_all_status()
    
    def print_status_report(self) -> None:
        """ステータスレポートを出力"""
        self.get_system_status()
        
        logger.info("=" * 80)
        logger.info("SYSTEM STATUS REPORT")
        logger.info("=" * 80)
        
        # Circuit Breakers
        if self.circuit_breakers:
            logger.info("\n[Circuit Breakers]")
            for name, breaker in self.circuit_breakers.items():
                metrics = breaker.get_metrics()
                logger.info(
                    f"  {name}: state={breaker.get_state().name}, "
                    f"success_rate={metrics.get_success_rate():.2f}%"
                )
        
        # Retry Managers
        if self.retry_managers:
            logger.info("\n[Retry Managers]")
            for name, manager in self.retry_managers.items():
                metrics = manager.get_metrics()
                logger.info(
                    f"  {name}: success_rate={metrics.get_success_rate():.2f}%, "
                    f"avg_retries={metrics.get_average_retry_count():.2f}"
                )
        
        # Failover Strategies
        if self.failover_strategies:
            logger.info("\n[Failover Strategies]")
            for name, strategy in self.failover_strategies.items():
                metrics = strategy.get_metrics()
                logger.info(
                    f"  {name}: total_requests={metrics.total_requests}, "
                    f"failovers={metrics.failover_count}, "
                    f"success_rate={metrics.get_success_rate():.2f}%"
                )
        
        # SLA Monitors
        if self.sla_monitors:
            logger.info("\n[SLA Monitors]")
            for name, monitor in self.sla_monitors.items():
                report = monitor.get_sla_report()
                logger.info(
                    f"  {name}: "
                    f"availability={report['availability']['actual']:.4f} "
                    f"(target={report['availability']['target']:.4f}), "
                    f"p99_latency={report['latency']['p99']['actual']:.1f}ms, "
                    f"error_rate={report['error_rate']['actual']:.4f}"
                )


# ============================================================================
# Utility Functions
# ============================================================================

def create_default_manager() -> ReliabilityManager:
    """デフォルト設定でReliabilityManagerを作成"""
    manager = ReliabilityManager()
    
    # Circuit Breaker作成
    manager.create_circuit_breaker(
        "api_gateway",
        failure_threshold=5,
        success_threshold=2,
        timeout=60
    )
    
    # Retry Manager作成
    manager.create_retry_manager(
        "database",
        max_retries=3,
        initial_delay=1.0,
        backoff_strategy="exponential"
    )
    
    # Failover Strategy作成
    manager.create_failover_strategy(
        "main_service",
        primary_url="http://primary:8000",
        backup_urls=["http://backup1:8000", "http://backup2:8000"]
    )
    
    # SLA Monitor作成
    manager.create_sla_monitor(
        "main_service",
        availability_target=0.9999,
        p99_latency=250.0,
        error_rate_threshold=0.01
    )
    
    return manager


# ============================================================================
# Demo Usage
# ============================================================================

async def demo():
    """デモンストレーション"""
    logger.info("Starting Phase 19 Task 1 Demo...")
    
    manager = create_default_manager()
    
    # 簡単なサービス関数
    async def simple_service(**kwargs):
        await asyncio.sleep(0.1)
        return "success"
    
    # ヘルスチェック関数
    async def health_check():
        await asyncio.sleep(0.05)
        return "healthy"
    
    # ヘルスチェックを登録
    await manager.register_health_check("main_service", health_check)
    
    # ヘルスチェックを開始
    await manager.start_all_health_checks()
    
    # Circuit Breaker経由でリクエスト実行
    breaker = manager.get_circuit_breaker("api_gateway")
    sla_monitor = manager.get_sla_monitor("main_service")
    
    for i in range(10):
        try:
            result = await breaker.call(simple_service)
            
            # SLAメトリクスを記録
            await sla_monitor.record_request(
                success=True,
                latency=100.0
            )
            
            logger.info(f"Request {i+1}: {result}")
        except Exception as e:
            logger.error(f"Request {i+1} failed: {e}")
            await sla_monitor.record_request(
                success=False,
                latency=0.0
            )
        
        await asyncio.sleep(0.5)
    
    # ステータスレポート出力
    manager.print_status_report()
    
    # ヘルスチェックを停止
    await manager.stop_all_health_checks()
    
    logger.info("Demo completed")


if __name__ == "__main__":
    asyncio.run(demo())
