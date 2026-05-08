"""
サービスメッシュ統合

Istio、Linkerd等のサービスメッシュ対応（基本インターフェース）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


class ServiceMeshType(Enum):
    """サービスメッシュタイプ"""
    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL = "consul"


class TrafficPolicy(Enum):
    """トラフィックポリシー"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    RANDOM = "random"
    RING_HASH = "ring_hash"


class MeshProtocol(Enum):
    """メッシュプロトコル"""
    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    TCP = "tcp"


@dataclass
class DestinationRule:
    """宛先ルール"""
    name: str
    namespace: str = "default"
    host: str = ""
    traffic_policy: TrafficPolicy = TrafficPolicy.ROUND_ROBIN
    outlier_detection_enabled: bool = True
    
    # 異常検出設定
    max_connections: int = 100
    max_requests: int = 100
    consecutive_errors: int = 5
    interval_seconds: int = 30


@dataclass
class VirtualService:
    """仮想サービス"""
    name: str
    namespace: str = "default"
    hosts: List[str] = field(default_factory=list)
    http_routes: List[Dict[str, Any]] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    retries_enabled: bool = True
    max_retries: int = 3


@dataclass
class ServiceEntry:
    """サービスエントリ"""
    name: str
    namespace: str = "default"
    hosts: List[str] = field(default_factory=list)
    ports: List[int] = field(default_factory=list)
    protocol: MeshProtocol = MeshProtocol.HTTP
    location: str = "MESH_INTERNAL"  # MESH_INTERNAL or MESH_EXTERNAL
    resolution: str = "STATIC"  # STATIC or DNS


class ServiceMeshAdapter:
    """サービスメッシュ適応レイヤー"""
    
    def __init__(self, mesh_type: ServiceMeshType):
        """初期化"""
        self.mesh_type = mesh_type
        self.destination_rules: Dict[str, DestinationRule] = {}
        self.virtual_services: Dict[str, VirtualService] = {}
        self.service_entries: Dict[str, ServiceEntry] = {}
        self.traffic_policies: Dict[str, Dict[str, Any]] = {}
    
    async def create_destination_rule(self, rule: DestinationRule) -> bool:
        """宛先ルールを作成"""
        
        key = f"{rule.namespace}/{rule.name}"
        
        if key in self.destination_rules:
            logger.warning(f"DestinationRule {key} already exists")
            return False
        
        self.destination_rules[key] = rule
        
        logger.info(f"DestinationRule created: {key} ({self.mesh_type.value})")
        
        return True
    
    async def delete_destination_rule(self, name: str, namespace: str = "default") -> bool:
        """宛先ルールを削除"""
        
        key = f"{namespace}/{name}"
        
        if key not in self.destination_rules:
            logger.warning(f"DestinationRule {key} not found")
            return False
        
        del self.destination_rules[key]
        
        logger.info(f"DestinationRule deleted: {key}")
        
        return True
    
    async def create_virtual_service(self, service: VirtualService) -> bool:
        """仮想サービスを作成"""
        
        key = f"{service.namespace}/{service.name}"
        
        if key in self.virtual_services:
            logger.warning(f"VirtualService {key} already exists")
            return False
        
        self.virtual_services[key] = service
        
        logger.info(f"VirtualService created: {key} ({self.mesh_type.value})")
        
        return True
    
    async def delete_virtual_service(self, name: str, namespace: str = "default") -> bool:
        """仮想サービスを削除"""
        
        key = f"{namespace}/{name}"
        
        if key not in self.virtual_services:
            logger.warning(f"VirtualService {key} not found")
            return False
        
        del self.virtual_services[key]
        
        logger.info(f"VirtualService deleted: {key}")
        
        return True
    
    async def register_external_service(self, entry: ServiceEntry) -> bool:
        """外部サービスを登録"""
        
        key = f"{entry.namespace}/{entry.name}"
        
        if key in self.service_entries:
            logger.warning(f"ServiceEntry {key} already exists")
            return False
        
        self.service_entries[key] = entry
        
        logger.info(f"ServiceEntry created: {key} ({entry.location})")
        
        return True
    
    async def configure_traffic_policy(
        self,
        service_name: str,
        policy: Dict[str, Any],
        namespace: str = "default"
    ) -> bool:
        """トラフィックポリシーを設定"""
        
        key = f"{namespace}/{service_name}"
        
        self.traffic_policies[key] = policy
        
        logger.info(f"Traffic policy configured: {key}")
        
        return True
    
    async def enable_retry_policy(
        self,
        service_name: str,
        max_retries: int = 3,
        retry_on: Optional[str] = None,
        namespace: str = "default"
    ) -> bool:
        """リトライポリシーを有効化"""
        
        retry_policy = {
            "max_retries": max_retries,
            "retry_on": retry_on or "5xx,reset,connect-failure,retriable-4xx",
            "backoff": "exponential"
        }
        
        return await self.configure_traffic_policy(
            service_name,
            retry_policy,
            namespace
        )
    
    async def enable_circuit_breaker(
        self,
        service_name: str,
        consecutive_errors: int = 5,
        interval_seconds: int = 30,
        namespace: str = "default"
    ) -> bool:
        """サーキットブレーカーを有効化"""
        
        # DestinationRuleを更新
        key = f"{namespace}/{service_name}"
        
        if key not in self.destination_rules:
            rule = DestinationRule(
                name=service_name,
                namespace=namespace,
                consecutive_errors=consecutive_errors,
                interval_seconds=interval_seconds
            )
            await self.create_destination_rule(rule)
        else:
            rule = self.destination_rules[key]
            rule.consecutive_errors = consecutive_errors
            rule.interval_seconds = interval_seconds
        
        logger.info(f"Circuit breaker enabled: {key}")
        
        return True
    
    async def enable_rate_limiting(
        self,
        service_name: str,
        requests_per_second: int = 100,
        namespace: str = "default"
    ) -> bool:
        """レート制限を有効化"""
        
        rate_limit_policy = {
            "requests_per_second": requests_per_second,
            "burst_size": requests_per_second * 2
        }
        
        return await self.configure_traffic_policy(
            service_name,
            rate_limit_policy,
            namespace
        )
    
    async def enable_timeout(
        self,
        service_name: str,
        timeout_seconds: int = 30,
        namespace: str = "default"
    ) -> bool:
        """タイムアウトを有効化"""
        
        timeout_policy = {
            "timeout": f"{timeout_seconds}s"
        }
        
        return await self.configure_traffic_policy(
            service_name,
            timeout_policy,
            namespace
        )


class MeshMetrics:
    """メッシュメトリクス"""
    
    def __init__(self):
        """初期化"""
        self.service_metrics: Dict[str, Dict[str, Any]] = {}
    
    async def record_request(
        self,
        source_service: str,
        dest_service: str,
        latency_ms: float,
        status_code: int,
        success: bool
    ) -> None:
        """リクエストを記録"""
        
        key = f"{source_service}->{dest_service}"
        
        if key not in self.service_metrics:
            self.service_metrics[key] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_latency_ms": 0,
                "min_latency_ms": float('inf'),
                "max_latency_ms": 0,
                "status_codes": {}
            }
        
        metrics = self.service_metrics[key]
        
        # リクエストカウント
        metrics["total_requests"] += 1
        
        if success:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1
        
        # レイテンシ
        metrics["total_latency_ms"] += latency_ms
        metrics["min_latency_ms"] = min(metrics["min_latency_ms"], latency_ms)
        metrics["max_latency_ms"] = max(metrics["max_latency_ms"], latency_ms)
        
        # ステータスコード
        status_key = str(status_code)
        metrics["status_codes"][status_key] = metrics["status_codes"].get(status_key, 0) + 1
    
    async def get_service_metrics(
        self,
        source_service: str,
        dest_service: str
    ) -> Dict[str, Any]:
        """サービス間のメトリクスを取得"""
        
        key = f"{source_service}->{dest_service}"
        
        if key not in self.service_metrics:
            return {}
        
        metrics = self.service_metrics[key]
        
        # 平均レイテンシ
        avg_latency = (
            metrics["total_latency_ms"] / metrics["total_requests"]
            if metrics["total_requests"] > 0
            else 0
        )
        
        # 成功率
        success_rate = (
            (metrics["successful_requests"] / metrics["total_requests"] * 100)
            if metrics["total_requests"] > 0
            else 0
        )
        
        return {
            "source_service": source_service,
            "dest_service": dest_service,
            "total_requests": metrics["total_requests"],
            "successful_requests": metrics["successful_requests"],
            "failed_requests": metrics["failed_requests"],
            "success_rate_percent": f"{success_rate:.1f}",
            "average_latency_ms": f"{avg_latency:.1f}",
            "min_latency_ms": f"{metrics['min_latency_ms']:.1f}",
            "max_latency_ms": f"{metrics['max_latency_ms']:.1f}",
            "status_code_distribution": metrics["status_codes"]
        }


class ServiceMeshController:
    """サービスメッシュコントローラー"""
    
    def __init__(self, mesh_type: ServiceMeshType):
        """初期化"""
        self.adapter = ServiceMeshAdapter(mesh_type)
        self.metrics = MeshMetrics()
    
    async def deploy_mesh_configuration(
        self,
        services: List[str],
        default_traffic_policy: TrafficPolicy = TrafficPolicy.ROUND_ROBIN
    ) -> bool:
        """メッシュ設定をデプロイ"""
        
        success = True
        
        for service in services:
            # 宛先ルール作成
            rule = DestinationRule(
                name=service,
                traffic_policy=default_traffic_policy
            )
            success &= await self.adapter.create_destination_rule(rule)
            
            # 仮想サービス作成
            vs = VirtualService(
                name=service,
                hosts=[service],
                retries_enabled=True
            )
            success &= await self.adapter.create_virtual_service(vs)
            
            logger.info(f"Mesh configuration deployed for: {service}")
        
        return success
    
    async def get_mesh_status(self) -> Dict[str, Any]:
        """メッシュ状態を取得"""
        
        return {
            "mesh_type": self.adapter.mesh_type.value,
            "destination_rules": len(self.adapter.destination_rules),
            "virtual_services": len(self.adapter.virtual_services),
            "service_entries": len(self.adapter.service_entries),
            "traffic_policies": len(self.adapter.traffic_policies),
            "total_requests": sum(
                m.get("total_requests", 0)
                for m in self.metrics.service_metrics.values()
            )
        }
