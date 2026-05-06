"""
サービスヘルスチェック・リカバリーシステム

継続的なヘルスモニタリングと自動リカバリーを提供
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import logging
import asyncio


logger = logging.getLogger(__name__)


class HealthCheckType(Enum):
    """ヘルスチェックタイプ"""
    LIVENESS = "liveness"      # サービスが動作中か
    READINESS = "readiness"    # リクエスト受け付け可能か
    STARTUP = "startup"        # 起動完了したか
    CUSTOM = "custom"          # カスタムチェック


class HealthStatus(Enum):
    """ヘルス状態"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """ヘルスチェック結果"""
    check_type: HealthCheckType
    status: HealthStatus
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    message: Optional[str] = None
    
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthHistory:
    """ヘルス履歴"""
    service_name: str
    
    results: List[HealthCheckResult] = field(default_factory=list)
    max_history_size: int = 1000
    
    last_check_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    def add_result(self, result: HealthCheckResult) -> None:
        """結果を追加"""
        self.results.append(result)
        self.last_check_time = result.timestamp
        
        # 履歴サイズを制限
        if len(self.results) > self.max_history_size:
            self.results = self.results[-self.max_history_size:]
        
        # 連続失敗/成功カウント
        if result.status == HealthStatus.HEALTHY:
            self.consecutive_failures = 0
            self.consecutive_successes += 1
        else:
            self.consecutive_successes = 0
            self.consecutive_failures += 1
    
    def get_health_trend(self, window_size: int = 10) -> Dict[str, Any]:
        """ヘルストレンドを取得"""
        if not self.results:
            return {"trend": "unknown", "health_rate": 0.0}
        
        # 最新のwindow_sizeの結果を確認
        recent = self.results[-window_size:]
        
        healthy_count = sum(
            1 for r in recent if r.status == HealthStatus.HEALTHY
        )
        health_rate = (healthy_count / len(recent)) * 100
        
        # トレンドを判定
        if len(recent) >= 3:
            recent_3 = recent[-3:]
            improving = sum(1 for r in recent_3 if r.status == HealthStatus.HEALTHY) >= 2
            trend = "improving" if improving else "degrading"
        else:
            trend = "unknown"
        
        return {
            "health_rate": health_rate,
            "trend": trend,
            "consecutive_healthy": self.consecutive_successes,
            "consecutive_unhealthy": self.consecutive_failures
        }


class HealthCheckManager:
    """ヘルスチェックマネージャー"""
    
    def __init__(self, service_name: str):
        """初期化"""
        self.service_name = service_name
        
        self.checks: Dict[HealthCheckType, Callable] = {}
        self.history = HealthHistory(service_name=service_name)
        
        self.check_interval_seconds = 5
        self.failure_threshold = 3
        
        self.is_monitoring = False
        self._monitor_task = None
    
    def register_check(
        self,
        check_type: HealthCheckType,
        check_func: Callable,
        timeout_seconds: int = 5
    ) -> None:
        """ヘルスチェック関数を登録"""
        self.checks[check_type] = (check_func, timeout_seconds)
        logger.info(f"Health check registered: {check_type.value}")
    
    async def perform_check(
        self,
        check_type: HealthCheckType
    ) -> Optional[HealthCheckResult]:
        """ヘルスチェックを実行"""
        
        if check_type not in self.checks:
            return None
        
        check_func, timeout_seconds = self.checks[check_type]
        
        try:
            import time
            start_time = time.time()
            
            # チェック関数を実行（タイムアウト付き）
            if asyncio.iscoroutinefunction(check_func):
                result = await asyncio.wait_for(
                    check_func(),
                    timeout=timeout_seconds
                )
            else:
                result = check_func()
            
            latency_ms = (time.time() - start_time) * 1000
            
            # 結果を構築
            status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
            
            check_result = HealthCheckResult(
                check_type=check_type,
                status=status,
                latency_ms=latency_ms,
                message="Check passed" if result else "Check failed"
            )
            
            self.history.add_result(check_result)
            return check_result
        
        except asyncio.TimeoutError:
            check_result = HealthCheckResult(
                check_type=check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timeout (>{timeout_seconds}s)"
            )
            self.history.add_result(check_result)
            return check_result
        
        except Exception as e:
            check_result = HealthCheckResult(
                check_type=check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check error: {str(e)}"
            )
            self.history.add_result(check_result)
            return check_result
    
    async def perform_all_checks(self) -> Dict[HealthCheckType, HealthCheckResult]:
        """すべてのチェックを実行"""
        
        results = {}
        
        for check_type in self.checks.keys():
            result = await self.perform_check(check_type)
            if result:
                results[check_type] = result
        
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """全体のヘルスステータスを取得"""
        
        if not self.history.results:
            return HealthStatus.UNKNOWN
        
        # 最新の結果を確認
        recent_results = self.history.results[-3:]
        
        unhealthy_count = sum(
            1 for r in recent_results if r.status != HealthStatus.HEALTHY
        )
        
        if unhealthy_count >= 2:
            return HealthStatus.UNHEALTHY
        elif unhealthy_count == 1:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def get_health_report(self) -> Dict[str, Any]:
        """ヘルスレポートを取得"""
        
        trend = self.history.get_health_trend()
        
        return {
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": self.get_overall_status().value,
            "health_history": {
                "consecutive_healthy": self.history.consecutive_successes,
                "consecutive_unhealthy": self.history.consecutive_failures,
                "total_checks": len(self.history.results),
                "health_rate": f"{trend['health_rate']:.1f}%"
            },
            "recent_checks": [
                {
                    "type": r.check_type.value,
                    "status": r.status.value,
                    "latency_ms": f"{r.latency_ms:.2f}",
                    "message": r.message
                }
                for r in self.history.results[-5:]
            ]
        }


class RecoveryStrategy:
    """リカバリー戦略"""
    
    def __init__(self, name: str):
        """初期化"""
        self.name = name
        self.recovery_actions: List[Callable] = []
    
    def add_action(self, action: Callable) -> None:
        """リカバリーアクションを追加"""
        self.recovery_actions.append(action)
    
    async def execute(self) -> bool:
        """リカバリーを実行"""
        
        try:
            for action in self.recovery_actions:
                if asyncio.iscoroutinefunction(action):
                    await action()
                else:
                    action()
            
            logger.info(f"Recovery strategy executed: {self.name}")
            return True
        
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return False


class HealthRecoveryManager:
    """ヘルス管理・リカバリーマネージャー"""
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 3
    ):
        """初期化"""
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        
        self.health_manager = HealthCheckManager(service_name)
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        
        self.last_recovery_time = None
        self.recovery_count = 0
    
    def register_recovery_strategy(
        self,
        strategy_name: str,
        strategy: RecoveryStrategy
    ) -> None:
        """リカバリー戦略を登録"""
        self.recovery_strategies[strategy_name] = strategy
    
    async def check_and_recover(self) -> Dict[str, Any]:
        """ヘルスチェックと必要なリカバリーを実行"""
        
        # ヘルスチェックを実行
        check_results = await self.health_manager.perform_all_checks()
        
        # 全体ステータスを判定
        overall_status = self.health_manager.get_overall_status()
        
        recovery_executed = False
        
        if overall_status == HealthStatus.UNHEALTHY:
            # リカバリーを実行
            if self.health_manager.history.consecutive_failures >= self.failure_threshold:
                
                # デフォルトリカバリー戦略を実行
                if "default" in self.recovery_strategies:
                    strategy = self.recovery_strategies["default"]
                    success = await strategy.execute()
                    
                    if success:
                        recovery_executed = True
                        self.last_recovery_time = datetime.utcnow()
                        self.recovery_count += 1
        
        return {
            "service_name": self.service_name,
            "overall_status": overall_status.value,
            "check_results": {
                k.value: v.status.value for k, v in check_results.items()
            },
            "recovery_executed": recovery_executed,
            "recovery_count": self.recovery_count,
            "timestamp": datetime.utcnow().isoformat()
        }
