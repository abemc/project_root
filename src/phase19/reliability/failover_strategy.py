"""
Failover Strategy Implementation

フェイルオーバー戦略の実装
"""

from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List, Dict
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServiceEndpoint:
    """サービスエンドポイント"""
    name: str
    url: str
    is_primary: bool = True
    priority: int = 0                    # 優先度（低いほど高優先度）
    health_check_interval: int = 10      # ヘルスチェック間隔（秒）
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    
    def should_check_health(self) -> bool:
        """ヘルスチェックを実施するべきかを判定"""
        if self.last_health_check is None:
            return True
        
        elapsed = (datetime.now() - self.last_health_check).total_seconds()
        return elapsed >= self.health_check_interval


@dataclass
class FailoverConfig:
    """フェイルオーバー設定"""
    primary: ServiceEndpoint
    backups: List[ServiceEndpoint] = field(default_factory=list)
    max_consecutive_failures: int = 3
    failover_timeout: float = 5.0       # フェイルオーバータイムアウト（秒）
    auto_recovery: bool = True          # 自動回復を有効にするか


@dataclass
class FailoverMetrics:
    """フェイルオーバーメトリクス"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    failover_count: int = 0
    failovers: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_success_rate(self) -> float:
        """成功率を取得"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


class FailoverStrategy:
    """
    フェイルオーバー戦略
    
    複数のサービスエンドポイントで冗長性を提供
    """
    
    def __init__(self, config: FailoverConfig):
        """初期化"""
        self.config = config
        self.endpoints = [config.primary] + config.backups
        self.current_endpoint: Optional[ServiceEndpoint] = None
        self.metrics = FailoverMetrics()
        self._lock = asyncio.Lock()
        self._health_check_tasks: List[asyncio.Task] = []
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        フェイルオーバー機能付きで関数を実行
        
        Args:
            func: 実行する関数
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            関数の実行結果
        """
        self.metrics.total_requests += 1
        
        # 利用可能なエンドポイントを取得
        available_endpoints = self._get_available_endpoints()
        
        if not available_endpoints:
            self.metrics.failed_requests += 1
            raise RuntimeError("No available endpoints")
        
        last_exception: Optional[Exception] = None
        
        for endpoint in available_endpoints:
            try:
                logger.info(f"Attempting request on {endpoint.name}...")
                
                # タイムアウト付きで関数を実行
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, endpoint=endpoint, **kwargs),
                        timeout=self.config.failover_timeout
                    )
                else:
                    result = func(*args, endpoint=endpoint, **kwargs)
                
                # 成功
                async with self._lock:
                    endpoint.is_healthy = True
                    endpoint.consecutive_failures = 0
                    endpoint.last_health_check = datetime.now()
                    self.metrics.successful_requests += 1
                
                logger.info(f"Request succeeded on {endpoint.name}")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Request failed on {endpoint.name}: {e}")
                
                # 失敗をカウント
                async with self._lock:
                    endpoint.consecutive_failures += 1
                    
                    if endpoint.consecutive_failures >= self.config.max_consecutive_failures:
                        endpoint.is_healthy = False
                        logger.error(
                            f"Endpoint {endpoint.name} marked as unhealthy "
                            f"(consecutive failures: {endpoint.consecutive_failures})"
                        )
                    
                    # フェイルオーバー記録
                    self.metrics.failover_count += 1
                    self.metrics.failovers.append({
                        "timestamp": datetime.now().isoformat(),
                        "from": endpoint.name,
                        "reason": str(e)
                    })
        
        # すべてのエンドポイントで失敗
        self.metrics.failed_requests += 1
        if last_exception:
            raise last_exception
        raise RuntimeError("All endpoints failed")
    
    def _get_available_endpoints(self) -> List[ServiceEndpoint]:
        """利用可能なエンドポイントを優先度順に取得"""
        available = [ep for ep in self.endpoints if ep.is_healthy]
        
        if not available:
            # 全エンドポイント利用不可の場合、プライマリを試みる
            logger.warning("No healthy endpoints, attempting primary...")
            available = [self.config.primary]
        
        # 優先度でソート
        available.sort(key=lambda ep: (not ep.is_primary, ep.priority))
        return available
    
    async def start_health_checks(self) -> None:
        """ヘルスチェックを開始"""
        logger.info("Starting health checks...")
        for endpoint in self.endpoints:
            task = asyncio.create_task(
                self._health_check_loop(endpoint)
            )
            self._health_check_tasks.append(task)
    
    async def stop_health_checks(self) -> None:
        """ヘルスチェックを停止"""
        logger.info("Stopping health checks...")
        for task in self._health_check_tasks:
            task.cancel()
        
        await asyncio.gather(*self._health_check_tasks, return_exceptions=True)
        self._health_check_tasks.clear()
    
    async def _health_check_loop(self, endpoint: ServiceEndpoint) -> None:
        """エンドポイントのヘルスチェックループ"""
        while True:
            try:
                if endpoint.should_check_health():
                    await self._perform_health_check(endpoint)
                
                await asyncio.sleep(endpoint.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for {endpoint.name}: {e}")
                await asyncio.sleep(endpoint.health_check_interval)
    
    async def _perform_health_check(self, endpoint: ServiceEndpoint) -> None:
        """ヘルスチェックを実行"""
        try:
            logger.debug(f"Performing health check for {endpoint.name}...")
            
            # 簡単なヘルスチェック（実装時にはHTTPリクエスト等）
            # ここではシンプルな実装
            endpoint.last_health_check = datetime.now()
            
            # エンドポイント情報をログ
            logger.debug(
                f"Health check OK: {endpoint.name} "
                f"(healthy={endpoint.is_healthy}, failures={endpoint.consecutive_failures})"
            )
            
        except Exception as e:
            logger.warning(f"Health check failed for {endpoint.name}: {e}")
            endpoint.is_healthy = False
    
    def get_metrics(self) -> FailoverMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def get_endpoint_status(self) -> Dict[str, Dict[str, Any]]:
        """全エンドポイントのステータスを取得"""
        status = {}
        for endpoint in self.endpoints:
            status[endpoint.name] = {
                "url": endpoint.url,
                "is_primary": endpoint.is_primary,
                "is_healthy": endpoint.is_healthy,
                "consecutive_failures": endpoint.consecutive_failures,
                "last_health_check": endpoint.last_health_check.isoformat() if endpoint.last_health_check else None,
            }
        return status
    
    async def mark_endpoint_healthy(self, endpoint_name: str) -> bool:
        """エンドポイントを手動で健全状態に設定"""
        for endpoint in self.endpoints:
            if endpoint.name == endpoint_name:
                async with self._lock:
                    endpoint.is_healthy = True
                    endpoint.consecutive_failures = 0
                    logger.info(f"Marked {endpoint_name} as healthy")
                return True
        return False
    
    async def mark_endpoint_unhealthy(self, endpoint_name: str) -> bool:
        """エンドポイントを手動で不健全状態に設定"""
        for endpoint in self.endpoints:
            if endpoint.name == endpoint_name:
                async with self._lock:
                    endpoint.is_healthy = False
                    logger.warning(f"Marked {endpoint_name} as unhealthy")
                return True
        return False
