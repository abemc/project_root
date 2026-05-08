"""
サービス間通信層

RPC/gRPC形式のサービス間通信を実現
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, List, Callable
import json
import logging
from http import HTTPStatus


logger = logging.getLogger(__name__)


class CommunicationProtocol(Enum):
    """通信プロトコル"""
    HTTP_REST = "http_rest"
    GRPC = "grpc"
    MESSAGE_QUEUE = "message_queue"


class RequestMethod(Enum):
    """リクエストメソッド"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class ServiceRequest:
    """サービスリクエスト"""
    service_name: str
    method: str
    path: str
    
    headers: Dict[str, str] = None
    body: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, str]] = None
    
    timeout_seconds: int = 30
    retry_count: int = 3
    
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.query_params is None:
            self.query_params = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ServiceResponse:
    """サービスレスポンス"""
    status_code: int
    body: Dict[str, Any]
    headers: Dict[str, str] = None
    
    latency_ms: float = 0.0
    timestamp: datetime = None
    
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    @property
    def is_success(self) -> bool:
        """成功判定"""
        return 200 <= self.status_code < 300
    
    @property
    def is_error(self) -> bool:
        """エラー判定"""
        return not self.is_success


class CircuitBreaker:
    """サーキットブレーカーパターン"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_seconds: int = 60
    ):
        """初期化"""
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_success(self) -> None:
        """成功を記録"""
        self.failure_count = 0
        
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = "CLOSED"
                self.success_count = 0
                logger.info("Circuit breaker CLOSED")
    
    def record_failure(self) -> None:
        """失敗を記録"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker OPEN")
    
    def is_available(self) -> bool:
        """利用可能判定"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            # タイムアウト後はHALF_OPENに遷移
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > self.timeout_seconds:
                self.state = "HALF_OPEN"
                self.success_count = 0
                logger.info("Circuit breaker HALF_OPEN")
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def get_state(self) -> str:
        """状態を取得"""
        return self.state


class RetryPolicy:
    """リトライポリシー"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_ms: int = 100,
        max_delay_ms: int = 10000,
        exponential_base: float = 2.0
    ):
        """初期化"""
        self.max_retries = max_retries
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
    
    def get_delay_ms(self, retry_count: int) -> int:
        """リトライ遅延を計算"""
        delay = self.initial_delay_ms * (self.exponential_base ** retry_count)
        return min(int(delay), self.max_delay_ms)
    
    def should_retry(self, retry_count: int, status_code: int) -> bool:
        """リトライすべきかを判定"""
        if retry_count >= self.max_retries:
            return False
        
        # 5xx エラーと タイムアウト時にリトライ
        return status_code >= 500 or status_code == 408


class ServiceCommunicationChannel(ABC):
    """サービス通信チャネル（抽象基本クラス）"""
    
    @abstractmethod
    async def send(self, request: ServiceRequest) -> ServiceResponse:
        """リクエストを送信"""
        pass


class HTTPRestChannel(ServiceCommunicationChannel):
    """HTTPレストチャネル"""
    
    def __init__(self, base_url: str):
        """初期化"""
        self.base_url = base_url
        self.circuit_breaker = CircuitBreaker()
        self.retry_policy = RetryPolicy()
    
    async def send(self, request: ServiceRequest) -> ServiceResponse:
        """HTTPリクエストを送信"""
        
        # サーキットブレーカーチェック
        if not self.circuit_breaker.is_available():
            return ServiceResponse(
                status_code=503,
                body={"error": "Service Unavailable (Circuit Open)"},
                error="Circuit breaker is open"
            )
        
        # リトライロジック
        last_response = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                # URLを構築
                url = f"{self.base_url}{request.path}"
                
                # シミュレートされたレスポンス
                response = await self._make_request(url, request)
                
                if response.is_success:
                    self.circuit_breaker.record_success()
                    return response
                else:
                    if self.retry_policy.should_retry(attempt, response.status_code):
                        delay_ms = self.retry_policy.get_delay_ms(attempt)
                        logger.info(f"Retry attempt {attempt + 1} after {delay_ms}ms")
                        # 実装では await asyncio.sleep(delay_ms / 1000.0) を使用
                    else:
                        self.circuit_breaker.record_failure()
                        return response
                
                last_response = response
            
            except Exception as e:
                logger.error(f"Communication error: {e}")
                self.circuit_breaker.record_failure()
                
                if attempt == self.retry_policy.max_retries:
                    return ServiceResponse(
                        status_code=503,
                        body={"error": str(e)},
                        error=str(e)
                    )
        
        return last_response or ServiceResponse(
            status_code=503,
            body={"error": "All retries failed"},
            error="All retries failed"
        )
    
    async def _make_request(self, url: str, request: ServiceRequest) -> ServiceResponse:
        """実際のHTTPリクエストを実行（シミュレーション）"""
        # 実装ではaiohttp/requests を使用
        return ServiceResponse(
            status_code=200,
            body={"success": True},
            latency_ms=50.0
        )


class LoadBalancedChannel(ServiceCommunicationChannel):
    """ロードバランシング済みチャネル"""
    
    def __init__(self, service_registry, load_balancer):
        """初期化"""
        self.service_registry = service_registry
        self.load_balancer = load_balancer
    
    async def send(self, request: ServiceRequest) -> ServiceResponse:
        """ロードバランシングしてリクエストを送信"""
        
        # 利用可能なインスタンスを取得
        instances = self.service_registry.discover(request.service_name)
        
        if not instances:
            return ServiceResponse(
                status_code=503,
                body={"error": "No available instances"},
                error="No available instances for service"
            )
        
        # ロードバランサーでインスタンスを選択
        instance = self.load_balancer.select(instances)
        
        if not instance:
            return ServiceResponse(
                status_code=503,
                body={"error": "Load balancer failed"},
                error="Failed to select instance"
            )
        
        # チャネルを作成して送信
        channel = HTTPRestChannel(instance.get_url())
        response = await channel.send(request)
        
        # ハートビートを更新
        if response.is_success:
            self.service_registry.heartbeat(instance.instance_id)
        else:
            self.service_registry.mark_unhealthy(instance.instance_id)
        
        return response


class ServiceCommunicationManager:
    """サービス通信マネージャー"""
    
    def __init__(self, service_registry=None):
        """初期化"""
        self.service_registry = service_registry
        self.channels: Dict[str, ServiceCommunicationChannel] = {}
    
    def register_channel(
        self,
        channel_name: str,
        channel: ServiceCommunicationChannel
    ) -> None:
        """チャネルを登録"""
        self.channels[channel_name] = channel
        logger.info(f"Communication channel registered: {channel_name}")
    
    async def send_request(
        self,
        channel_name: str,
        request: ServiceRequest
    ) -> ServiceResponse:
        """リクエストを送信"""
        
        if channel_name not in self.channels:
            return ServiceResponse(
                status_code=404,
                body={"error": "Channel not found"},
                error=f"Channel {channel_name} not found"
            )
        
        channel = self.channels[channel_name]
        
        # リクエスト開始時刻
        import time
        start_time = time.time()
        
        try:
            response = await channel.send(request)
            
            # レイテンシを計算
            response.latency_ms = (time.time() - start_time) * 1000
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            return ServiceResponse(
                status_code=500,
                body={"error": str(e)},
                error=str(e)
            )
