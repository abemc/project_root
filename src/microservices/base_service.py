"""
マイクロサービス基本クラス

すべてのサービスが継承する基本的な機能を提供
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import uuid
import logging


logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """サービスステータス"""
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServiceLogLevel(Enum):
    """ログレベル"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ServiceConfig:
    """サービス設定"""
    name: str
    version: str = "1.0.0"
    instance_id: Optional[str] = None
    
    # リソース設定
    max_workers: int = 10
    max_queue_size: int = 1000
    request_timeout_seconds: int = 30
    
    # ヘルスチェック設定
    health_check_interval_seconds: int = 5
    health_check_timeout_seconds: int = 2
    unhealthy_threshold: int = 3
    
    # ロギング設定
    log_level: ServiceLogLevel = ServiceLogLevel.INFO
    enable_metrics: bool = True
    enable_tracing: bool = False
    
    def __post_init__(self):
        if self.instance_id is None:
            self.instance_id = str(uuid.uuid4())[:8]


@dataclass
class ServiceMetrics:
    """サービスメトリクス"""
    service_name: str
    instance_id: str
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    average_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.total_requests
        return (self.successful_requests / total * 100) if total > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """エラー率"""
        return 100.0 - self.success_rate
    
    @property
    def uptime_seconds(self) -> float:
        """稼働時間（秒）"""
        return (datetime.utcnow() - self.start_time).total_seconds()


@dataclass
class ServiceHealthStatus:
    """サービスヘルスステータス"""
    service_name: str
    instance_id: str
    status: ServiceStatus
    
    is_healthy: bool
    consecutive_failures: int = 0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    
    metrics: Optional[ServiceMetrics] = None
    
    @property
    def health_percentage(self) -> float:
        """ヘルス率（0-100%）"""
        if self.status == ServiceStatus.HEALTHY:
            return 100.0
        elif self.status == ServiceStatus.RUNNING:
            return 90.0
        elif self.status == ServiceStatus.DEGRADED:
            return 70.0
        elif self.status == ServiceStatus.UNHEALTHY:
            return 0.0
        else:
            return 50.0


class ServiceBase(ABC):
    """サービス基本クラス"""
    
    def __init__(self, config: ServiceConfig):
        """初期化"""
        self.config = config
        self.status = ServiceStatus.STARTING
        
        self.metrics = ServiceMetrics(
            service_name=config.name,
            instance_id=config.instance_id
        )
        
        self.health_status = ServiceHealthStatus(
            service_name=config.name,
            instance_id=config.instance_id,
            status=ServiceStatus.STARTING,
            is_healthy=True
        )
        
        self._middleware: List[Callable] = []
        self._error_handlers: Dict[type, Callable] = {}
        self._health_checks: List[Callable] = []
    
    @abstractmethod
    async def initialize(self) -> bool:
        """サービスを初期化"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """サービスをシャットダウン"""
        pass
    
    async def start(self) -> bool:
        """サービスを開始"""
        try:
            self.status = ServiceStatus.STARTING
            logger.info(f"Starting service: {self.config.name}")
            
            # 初期化
            if not await self.initialize():
                self.status = ServiceStatus.UNHEALTHY
                return False
            
            self.status = ServiceStatus.RUNNING
            logger.info(f"Service started: {self.config.name}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            self.status = ServiceStatus.UNHEALTHY
            return False
    
    async def stop(self) -> None:
        """サービスを停止"""
        try:
            self.status = ServiceStatus.STOPPING
            logger.info(f"Stopping service: {self.config.name}")
            
            await self.shutdown()
            
            self.status = ServiceStatus.STOPPED
            logger.info(f"Service stopped: {self.config.name}")
        
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            self.status = ServiceStatus.UNHEALTHY
    
    def add_middleware(self, middleware: Callable) -> None:
        """ミドルウェアを追加"""
        self._middleware.append(middleware)
    
    def register_error_handler(self, exception_type: type, handler: Callable) -> None:
        """エラーハンドラーを登録"""
        self._error_handlers[exception_type] = handler
    
    def register_health_check(self, check: Callable) -> None:
        """ヘルスチェック関数を登録"""
        self._health_checks.append(check)
    
    async def perform_health_check(self) -> ServiceHealthStatus:
        """ヘルスチェックを実行"""
        try:
            # すべてのヘルスチェック関数を実行
            for check in self._health_checks:
                result = await check() if hasattr(check, '__await__') else check()
                if not result:
                    self.health_status.is_healthy = False
                    self.health_status.consecutive_failures += 1
                    
                    if self.health_status.consecutive_failures >= self.config.unhealthy_threshold:
                        self.status = ServiceStatus.UNHEALTHY
                    else:
                        self.status = ServiceStatus.DEGRADED
                    
                    return self.health_status
            
            # すべてのチェックが成功
            self.health_status.is_healthy = True
            self.health_status.consecutive_failures = 0
            self.status = ServiceStatus.HEALTHY
            
            return self.health_status
        
        except Exception as e:
            logger.error(f"Health check error: {e}")
            self.health_status.is_healthy = False
            self.health_status.consecutive_failures += 1
            self.status = ServiceStatus.UNHEALTHY
            
            return self.health_status
    
    def record_request(self, latency_ms: float, success: bool = True) -> None:
        """リクエストを記録"""
        self.metrics.total_requests += 1
        
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # レイテンシを更新
        if self.metrics.total_requests == 1:
            self.metrics.min_latency_ms = latency_ms
            self.metrics.max_latency_ms = latency_ms
            self.metrics.average_latency_ms = latency_ms
        else:
            prev_avg = self.metrics.average_latency_ms
            self.metrics.average_latency_ms = (
                prev_avg * (self.metrics.total_requests - 1) + latency_ms
            ) / self.metrics.total_requests
            self.metrics.min_latency_ms = min(self.metrics.min_latency_ms, latency_ms)
            self.metrics.max_latency_ms = max(self.metrics.max_latency_ms, latency_ms)
        
        self.metrics.last_update = datetime.utcnow()
    
    def get_metrics(self) -> ServiceMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def get_health_status(self) -> ServiceHealthStatus:
        """ヘルスステータスを取得"""
        self.health_status.metrics = self.metrics
        return self.health_status
    
    def get_status_report(self) -> Dict[str, Any]:
        """ステータスレポートを取得"""
        health = self.get_health_status()
        
        return {
            "name": self.config.name,
            "version": self.config.version,
            "instance_id": self.config.instance_id,
            "status": self.status.value,
            "is_healthy": health.is_healthy,
            "health_percentage": health.health_percentage,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "success_rate": f"{self.metrics.success_rate:.2f}%",
                "average_latency_ms": f"{self.metrics.average_latency_ms:.2f}",
                "uptime_seconds": f"{self.metrics.uptime_seconds:.1f}"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
