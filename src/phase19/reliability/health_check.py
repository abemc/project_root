"""
Health Check Implementation

サービスのヘルスチェック機能
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """ヘルスチェック結果"""
    service_name: str
    is_healthy: bool
    status_code: Optional[int] = None
    response_time: float = 0.0  # ミリ秒
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "service_name": self.service_name,
            "is_healthy": self.is_healthy,
            "status_code": self.status_code,
            "response_time": f"{self.response_time:.2f}ms",
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthCheckConfig:
    """ヘルスチェック設定"""
    interval: int = 10                      # チェック間隔（秒）
    timeout: float = 5.0                   # タイムアウト（秒）
    healthy_threshold: int = 1             # 健全と判定するまでの成功回数
    unhealthy_threshold: int = 3           # 不健全と判定するまでの失敗回数
    check_timeout_as_failure: bool = True  # タイムアウトを失敗と見なすか


class HealthChecker:
    """
    ヘルスチェック機能
    
    サービスの健全性を定期的に監視
    """
    
    def __init__(
        self,
        service_name: str,
        check_func: Callable,
        config: Optional[HealthCheckConfig] = None
    ):
        """初期化"""
        self.service_name = service_name
        self.check_func = check_func
        self.config = config or HealthCheckConfig()
        self.is_healthy = True
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.last_check_result: Optional[HealthCheckResult] = None
        self.check_history: List[HealthCheckResult] = []
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """ヘルスチェックを開始"""
        logger.info(f"Starting health checks for {self.service_name}")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._check_loop())
    
    async def stop(self) -> None:
        """ヘルスチェックを停止"""
        logger.info(f"Stopping health checks for {self.service_name}")
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _check_loop(self) -> None:
        """ヘルスチェックループ"""
        while True:
            try:
                await self.check()
                await asyncio.sleep(self.config.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.config.interval)
    
    async def check(self) -> HealthCheckResult:
        """ヘルスチェックを実行"""
        start_time = datetime.now()
        
        try:
            # チェック関数を実行
            if asyncio.iscoroutinefunction(self.check_func):
                await asyncio.wait_for(
                    self.check_func(),
                    timeout=self.config.timeout
                )
            else:
                self.check_func()
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # 結果を処理
            check_result = HealthCheckResult(
                service_name=self.service_name,
                is_healthy=True,
                response_time=response_time,
                error_message=None,
            )
            
            # ステータス更新
            await self._on_check_success(check_result)
            
            return check_result
            
        except asyncio.TimeoutError:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            check_result = HealthCheckResult(
                service_name=self.service_name,
                is_healthy=False,
                response_time=response_time,
                error_message="Health check timeout",
            )
            
            await self._on_check_failure(check_result)
            return check_result
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            check_result = HealthCheckResult(
                service_name=self.service_name,
                is_healthy=False,
                response_time=response_time,
                error_message=str(e),
            )
            
            await self._on_check_failure(check_result)
            return check_result
    
    async def _on_check_success(self, result: HealthCheckResult) -> None:
        """チェック成功時の処理"""
        async with self._lock:
            self.consecutive_failures = 0
            self.consecutive_successes += 1
            
            # 健全な状態に遷移
            if self.consecutive_successes >= self.config.healthy_threshold and not self.is_healthy:
                self.is_healthy = True
                logger.info(
                    f"{self.service_name} is now HEALTHY "
                    f"(consecutive successes: {self.consecutive_successes})"
                )
            
            self.last_check_result = result
            self.check_history.append(result)
            
            # 履歴を100件まで保持
            if len(self.check_history) > 100:
                self.check_history = self.check_history[-100:]
    
    async def _on_check_failure(self, result: HealthCheckResult) -> None:
        """チェック失敗時の処理"""
        async with self._lock:
            self.consecutive_successes = 0
            self.consecutive_failures += 1
            
            # 不健全な状態に遷移
            if self.consecutive_failures >= self.config.unhealthy_threshold and self.is_healthy:
                self.is_healthy = False
                logger.error(
                    f"{self.service_name} is now UNHEALTHY "
                    f"(consecutive failures: {self.consecutive_failures}) - {result.error_message}"
                )
            
            self.last_check_result = result
            self.check_history.append(result)
            
            # 履歴を100件まで保持
            if len(self.check_history) > 100:
                self.check_history = self.check_history[-100:]
    
    def get_status(self) -> Dict[str, Any]:
        """ステータスを取得"""
        return {
            "service_name": self.service_name,
            "is_healthy": self.is_healthy,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check_result.to_dict() if self.last_check_result else None,
        }
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """チェック履歴を取得"""
        return [
            result.to_dict()
            for result in self.check_history[-limit:]
        ]


class HealthCheckRegistry:
    """複数のヘルスチェッカーを管理"""
    
    def __init__(self):
        """初期化"""
        self.checkers: Dict[str, HealthChecker] = {}
        self._lock = asyncio.Lock()
    
    async def register(
        self,
        service_name: str,
        check_func: Callable,
        config: Optional[HealthCheckConfig] = None
    ) -> HealthChecker:
        """ヘルスチェッカーを登録"""
        async with self._lock:
            if service_name in self.checkers:
                logger.warning(f"HealthChecker for {service_name} already registered")
                return self.checkers[service_name]
            
            checker = HealthChecker(service_name, check_func, config)
            self.checkers[service_name] = checker
            logger.info(f"Registered HealthChecker for {service_name}")
            return checker
    
    async def get(self, service_name: str) -> Optional[HealthChecker]:
        """ヘルスチェッカーを取得"""
        return self.checkers.get(service_name)
    
    async def start_all(self) -> None:
        """全ヘルスチェッカーを開始"""
        logger.info("Starting all health checkers...")
        for checker in self.checkers.values():
            await checker.start()
    
    async def stop_all(self) -> None:
        """全ヘルスチェッカーを停止"""
        logger.info("Stopping all health checkers...")
        for checker in self.checkers.values():
            await checker.stop()
    
    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """全サービスのステータスを取得"""
        status = {}
        for service_name, checker in self.checkers.items():
            status[service_name] = checker.get_status()
        return status
    
    def get_healthy_services(self) -> List[str]:
        """健全なサービスの一覧を取得"""
        return [
            name for name, checker in self.checkers.items()
            if checker.is_healthy
        ]
    
    def get_unhealthy_services(self) -> List[str]:
        """不健全なサービスの一覧を取得"""
        return [
            name for name, checker in self.checkers.items()
            if not checker.is_healthy
        ]


# グローバルレジストリ
_global_registry = HealthCheckRegistry()


async def register_health_check(
    service_name: str,
    check_func: Callable,
    config: Optional[HealthCheckConfig] = None
) -> HealthChecker:
    """グローバルレジストリにヘルスチェッカーを登録"""
    return await _global_registry.register(service_name, check_func, config)


async def get_health_check(service_name: str) -> Optional[HealthChecker]:
    """グローバルレジストリからヘルスチェッカーを取得"""
    return await _global_registry.get(service_name)


async def start_all_health_checks() -> None:
    """全ヘルスチェッカーを開始"""
    await _global_registry.start_all()


async def stop_all_health_checks() -> None:
    """全ヘルスチェッカーを停止"""
    await _global_registry.stop_all()


async def get_all_health_status() -> Dict[str, Dict[str, Any]]:
    """全サービスのヘルスチェックステータスを取得"""
    return await _global_registry.get_all_status()
