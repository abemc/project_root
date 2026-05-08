"""
ロードバランサー

複数のサービスインスタンス間でのリクエスト分配を実現
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import logging
import random
import heapq


logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """ロードバランシング戦略"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    IP_HASH = "ip_hash"
    RANDOM = "random"
    WEIGHTED = "weighted"


@dataclass
class InstanceMetrics:
    """インスタンスメトリクス"""
    instance_id: str
    active_connections: int = 0
    total_requests: int = 0
    average_response_time_ms: float = 0.0
    error_count: int = 0
    last_used_time: Optional[datetime] = None
    
    weight: int = 1  # 重み付け（加重ロードバランシング用）
    
    @property
    def health_score(self) -> float:
        """ヘルススコア（0-100）"""
        if self.total_requests == 0:
            return 100.0
        
        # エラー率
        error_rate = (self.error_count / self.total_requests) * 100
        
        # レスポンスタイム（相対的）
        response_penalty = min(self.average_response_time_ms / 1000, 10) * 5
        
        score = 100 - error_rate - response_penalty
        return max(score, 0.0)
    
    @property
    def utilization_score(self) -> float:
        """利用率スコア（0-100）"""
        # 接続数が多いほどスコアが低い
        return max(0, 100 - (self.active_connections * 10))


class LoadBalancerBase(ABC):
    """ロードバランサー基本クラス"""
    
    def __init__(self, strategy: LoadBalancingStrategy):
        """初期化"""
        self.strategy = strategy
        self.metrics: Dict[str, InstanceMetrics] = {}
    
    @abstractmethod
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        pass
    
    def register_instance_metrics(
        self,
        instance_id: str,
        weight: int = 1
    ) -> None:
        """インスタンスメトリクスを登録"""
        self.metrics[instance_id] = InstanceMetrics(
            instance_id=instance_id,
            weight=weight
        )
    
    def update_metrics(
        self,
        instance_id: str,
        latency_ms: float,
        success: bool
    ) -> None:
        """メトリクスを更新"""
        
        if instance_id not in self.metrics:
            self.register_instance_metrics(instance_id)
        
        metrics = self.metrics[instance_id]
        
        # リクエストカウント更新
        metrics.total_requests += 1
        
        # エラーカウント更新
        if not success:
            metrics.error_count += 1
        
        # 平均レスポンスタイム更新
        prev_avg = metrics.average_response_time_ms
        metrics.average_response_time_ms = (
            (prev_avg * (metrics.total_requests - 1) + latency_ms) /
            metrics.total_requests
        )
        
        # 最後使用時刻更新
        metrics.last_used_time = datetime.utcnow()
    
    def increment_connection(self, instance_id: str) -> None:
        """接続数をインクリメント"""
        if instance_id in self.metrics:
            self.metrics[instance_id].active_connections += 1
    
    def decrement_connection(self, instance_id: str) -> None:
        """接続数をデクリメント"""
        if instance_id in self.metrics:
            self.metrics[instance_id].active_connections = max(
                0,
                self.metrics[instance_id].active_connections - 1
            )


class RoundRobinLoadBalancer(LoadBalancerBase):
    """ラウンドロビンロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.ROUND_ROBIN)
        self.current_index = 0
    
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        # ラウンドロビンで選択
        selected = valid_instances[self.current_index % len(valid_instances)]
        self.current_index = (self.current_index + 1) % len(valid_instances)
        
        return selected


class LeastConnectionsLoadBalancer(LoadBalancerBase):
    """最少接続ロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.LEAST_CONNECTIONS)
    
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        # 最少接続数のインスタンスを選択
        best_instance = None
        min_connections = float('inf')
        
        for instance in valid_instances:
            instance_id = instance.instance_id
            connections = 0
            
            if instance_id in self.metrics:
                connections = self.metrics[instance_id].active_connections
            
            if connections < min_connections:
                min_connections = connections
                best_instance = instance
        
        return best_instance


class LeastResponseTimeLoadBalancer(LoadBalancerBase):
    """最小レスポンスタイムロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.LEAST_RESPONSE_TIME)
    
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        # 最小レスポンスタイムのインスタンスを選択
        best_instance = None
        min_response_time = float('inf')
        
        for instance in valid_instances:
            instance_id = instance.instance_id
            response_time = 0
            
            if instance_id in self.metrics:
                response_time = self.metrics[instance_id].average_response_time_ms
            
            if response_time < min_response_time:
                min_response_time = response_time
                best_instance = instance
        
        return best_instance


class WeightedLoadBalancer(LoadBalancerBase):
    """加重ロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.WEIGHTED)
        self.current_index = 0
    
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        # 加重を考慮して選択
        total_weight = 0
        candidates = []
        
        for instance in valid_instances:
            instance_id = instance.instance_id
            weight = 1
            
            if instance_id in self.metrics:
                weight = self.metrics[instance_id].weight
            
            total_weight += weight
            candidates.append((weight, instance))
        
        # ランダムに選択（加重に基づいて）
        if total_weight <= 0:
            return valid_instances[0]
        
        choice = random.uniform(0, total_weight)
        current = 0
        
        for weight, instance in candidates:
            current += weight
            if choice <= current:
                return instance
        
        return candidates[-1][1]


class RandomLoadBalancer(LoadBalancerBase):
    """ランダムロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.RANDOM)
    
    def select(self, instances: List[Any]) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        return random.choice(valid_instances)


class IPHashLoadBalancer(LoadBalancerBase):
    """IPハッシュロードバランサー"""
    
    def __init__(self):
        """初期化"""
        super().__init__(LoadBalancingStrategy.IP_HASH)
    
    def select(self, instances: List[Any], client_ip: Optional[str] = None) -> Optional[Any]:
        """インスタンスを選択"""
        
        if not instances:
            return None
        
        # フィルター: 有効なインスタンスのみ
        valid_instances = [i for i in instances if hasattr(i, 'is_alive') and i.is_alive()]
        
        if not valid_instances:
            return instances[0] if instances else None
        
        # クライアントIPでハッシュ
        if client_ip is None:
            client_ip = "default"
        
        hash_value = hash(client_ip)
        index = hash_value % len(valid_instances)
        
        return valid_instances[index]


class LoadBalancerFactory:
    """ロードバランサーファクトリー"""
    
    @staticmethod
    def create(strategy: LoadBalancingStrategy) -> LoadBalancerBase:
        """ロードバランサーを作成"""
        
        if strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return RoundRobinLoadBalancer()
        elif strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return LeastConnectionsLoadBalancer()
        elif strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
            return LeastResponseTimeLoadBalancer()
        elif strategy == LoadBalancingStrategy.WEIGHTED:
            return WeightedLoadBalancer()
        elif strategy == LoadBalancingStrategy.RANDOM:
            return RandomLoadBalancer()
        elif strategy == LoadBalancingStrategy.IP_HASH:
            return IPHashLoadBalancer()
        else:
            return RoundRobinLoadBalancer()  # デフォルト


class LoadBalancerManager:
    """ロードバランサー管理"""
    
    def __init__(self):
        """初期化"""
        self.balancers: Dict[str, LoadBalancerBase] = {}
    
    def create_balancer(
        self,
        name: str,
        strategy: LoadBalancingStrategy
    ) -> LoadBalancerBase:
        """ロードバランサーを作成"""
        
        balancer = LoadBalancerFactory.create(strategy)
        self.balancers[name] = balancer
        
        logger.info(f"Load balancer created: {name} ({strategy.value})")
        
        return balancer
    
    def get_balancer(self, name: str) -> Optional[LoadBalancerBase]:
        """ロードバランサーを取得"""
        return self.balancers.get(name)
    
    def get_report(self) -> Dict[str, Any]:
        """レポートを取得"""
        
        report = {}
        
        for name, balancer in self.balancers.items():
            metrics_summary = []
            
            for instance_id, metrics in balancer.metrics.items():
                metrics_summary.append({
                    "instance_id": instance_id,
                    "active_connections": metrics.active_connections,
                    "total_requests": metrics.total_requests,
                    "average_response_time_ms": f"{metrics.average_response_time_ms:.2f}",
                    "error_count": metrics.error_count,
                    "health_score": f"{metrics.health_score:.1f}"
                })
            
            report[name] = {
                "strategy": balancer.strategy.value,
                "instances": metrics_summary
            }
        
        return report
