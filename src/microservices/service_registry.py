"""
サービスレジストリ

サービスの発見・登録・管理を行うレジストリシステム
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid
import logging
from threading import RLock


logger = logging.getLogger(__name__)


class ServiceRegistrationStatus(Enum):
    """サービス登録ステータス"""
    PENDING = "pending"
    REGISTERED = "registered"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEREGISTERED = "deregistered"


class DiscoveryMethod(Enum):
    """サービス発見方式"""
    DIRECT = "direct"  # 直接指定
    DNS = "dns"  # DNSベース
    CONSUL = "consul"  # Consulベース
    KUBERNETES = "kubernetes"  # Kubernetesベース


@dataclass
class ServiceInstance:
    """サービスインスタンス"""
    service_name: str
    instance_id: str
    host: str
    port: int
    
    metadata: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    status: ServiceRegistrationStatus = ServiceRegistrationStatus.PENDING
    registration_time: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    
    # ハートビート設定
    heartbeat_interval_seconds: int = 10
    heartbeat_timeout_seconds: int = 30
    
    def is_alive(self, timeout_seconds: Optional[int] = None) -> bool:
        """インスタンスが有効かチェック"""
        timeout = timeout_seconds or self.heartbeat_timeout_seconds
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed < timeout
    
    def update_heartbeat(self) -> None:
        """ハートビートを更新"""
        self.last_heartbeat = datetime.utcnow()
    
    def get_url(self) -> str:
        """インスタンスURLを取得"""
        return f"http://{self.host}:{self.port}"


@dataclass
class ServiceRegistryStats:
    """レジストリ統計"""
    total_services: int = 0
    total_instances: int = 0
    healthy_instances: int = 0
    unhealthy_instances: int = 0
    
    @property
    def health_rate(self) -> float:
        """ヘルス率"""
        if self.total_instances == 0:
            return 0.0
        return (self.healthy_instances / self.total_instances) * 100


class ServiceRegistry:
    """サービスレジストリ"""
    
    def __init__(self, max_heartbeat_timeout_seconds: int = 30):
        """初期化"""
        self.max_heartbeat_timeout = max_heartbeat_timeout_seconds
        
        # サービス名 -> インスタンスリスト
        self._services: Dict[str, List[ServiceInstance]] = {}
        
        # インスタンスID -> インスタンス
        self._instances: Dict[str, ServiceInstance] = {}
        
        # ロック
        self._lock = RLock()
    
    def register(
        self,
        service_name: str,
        host: str,
        port: int,
        metadata: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        instance_id: Optional[str] = None
    ) -> ServiceInstance:
        """サービスインスタンスを登録"""
        
        with self._lock:
            # インスタンスIDを生成
            if instance_id is None:
                instance_id = str(uuid.uuid4())[:12]
            
            # インスタンスを作成
            instance = ServiceInstance(
                service_name=service_name,
                instance_id=instance_id,
                host=host,
                port=port,
                metadata=metadata or {},
                tags=tags or []
            )
            
            # レジストリに追加
            if service_name not in self._services:
                self._services[service_name] = []
            
            self._services[service_name].append(instance)
            self._instances[instance_id] = instance
            
            instance.status = ServiceRegistrationStatus.REGISTERED
            instance.update_heartbeat()
            
            logger.info(f"Service registered: {service_name}/{instance_id} at {host}:{port}")
            
            return instance
    
    def deregister(self, service_name: str, instance_id: str) -> bool:
        """サービスインスタンスを登録解除"""
        
        with self._lock:
            if service_name not in self._services:
                return False
            
            # インスタンスを削除
            instances = self._services[service_name]
            instance_to_remove = None
            
            for instance in instances:
                if instance.instance_id == instance_id:
                    instance_to_remove = instance
                    instance.status = ServiceRegistrationStatus.DEREGISTERED
                    break
            
            if instance_to_remove:
                instances.remove(instance_to_remove)
                del self._instances[instance_id]
                
                # サービスが空になったら削除
                if not instances:
                    del self._services[service_name]
                
                logger.info(f"Service deregistered: {service_name}/{instance_id}")
                return True
            
            return False
    
    def discover(
        self,
        service_name: str,
        healthy_only: bool = True
    ) -> List[ServiceInstance]:
        """サービスインスタンスを発見"""
        
        with self._lock:
            if service_name not in self._services:
                return []
            
            instances = self._services[service_name]
            
            if healthy_only:
                # 有効なインスタンスのみ返す
                return [inst for inst in instances if inst.is_alive()]
            
            return instances
    
    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """インスタンスを取得"""
        
        with self._lock:
            return self._instances.get(instance_id)
    
    def heartbeat(self, instance_id: str) -> bool:
        """ハートビートを更新"""
        
        with self._lock:
            instance = self._instances.get(instance_id)
            
            if instance is None:
                return False
            
            instance.update_heartbeat()
            
            # ステータスを更新
            if instance.is_alive():
                if instance.status != ServiceRegistrationStatus.HEALTHY:
                    instance.status = ServiceRegistrationStatus.HEALTHY
                    logger.info(f"Instance became healthy: {instance.instance_id}")
            
            return True
    
    def mark_unhealthy(self, instance_id: str) -> bool:
        """インスタンスを不健康とマーク"""
        
        with self._lock:
            instance = self._instances.get(instance_id)
            
            if instance is None:
                return False
            
            instance.status = ServiceRegistrationStatus.UNHEALTHY
            logger.warning(f"Instance marked unhealthy: {instance_id}")
            
            return True
    
    def get_stats(self) -> ServiceRegistryStats:
        """レジストリ統計を取得"""
        
        with self._lock:
            stats = ServiceRegistryStats()
            
            stats.total_services = len(self._services)
            stats.total_instances = len(self._instances)
            
            for instance in self._instances.values():
                if instance.is_alive():
                    stats.healthy_instances += 1
                else:
                    stats.unhealthy_instances += 1
            
            return stats
    
    def cleanup_dead_instances(self) -> int:
        """不健康なインスタンスをクリーンアップ"""
        
        with self._lock:
            removed_count = 0
            services_to_clean = []
            
            for service_name, instances in self._services.items():
                alive_instances = []
                
                for instance in instances:
                    if instance.is_alive(self.max_heartbeat_timeout):
                        alive_instances.append(instance)
                    else:
                        del self._instances[instance.instance_id]
                        removed_count += 1
                        logger.warning(
                            f"Removed dead instance: {service_name}/{instance.instance_id}"
                        )
                
                if alive_instances:
                    self._services[service_name] = alive_instances
                else:
                    services_to_clean.append(service_name)
            
            # 空のサービスを削除
            for service_name in services_to_clean:
                del self._services[service_name]
            
            return removed_count
    
    def get_registry_report(self) -> Dict[str, Any]:
        """レジストリレポートを取得"""
        
        with self._lock:
            stats = self.get_stats()
            
            services_info = {}
            for service_name, instances in self._services.items():
                services_info[service_name] = {
                    "instance_count": len(instances),
                    "healthy_count": sum(1 for i in instances if i.is_alive()),
                    "instances": [
                        {
                            "id": i.instance_id,
                            "url": i.get_url(),
                            "status": i.status.value,
                            "tags": i.tags
                        }
                        for i in instances
                    ]
                }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "stats": {
                    "total_services": stats.total_services,
                    "total_instances": stats.total_instances,
                    "healthy_instances": stats.healthy_instances,
                    "health_rate": f"{stats.health_rate:.1f}%"
                },
                "services": services_info
            }
