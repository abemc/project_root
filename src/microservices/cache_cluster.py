"""
キャッシュクラスタ管理

複数のキャッシュノード間での同期・レプリケーション管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import asyncio
import logging


logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """ノードロール"""
    PRIMARY = "primary"
    REPLICA = "replica"
    BACKUP = "backup"


class ReplicationMode(Enum):
    """レプリケーションモード"""
    SYNCHRONOUS = "synchronous"  # 同期
    ASYNCHRONOUS = "asynchronous"  # 非同期
    SEMI_SYNCHRONOUS = "semi_synchronous"  # 準同期


@dataclass
class CacheNode:
    """キャッシュノード"""
    node_id: str
    host: str
    port: int
    role: NodeRole = NodeRole.REPLICA
    is_healthy: bool = True
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    replicated_entries: int = 0
    replication_lag_ms: float = 0.0
    
    @property
    def is_alive(self, timeout_seconds: int = 30) -> bool:
        """ノード生存確認"""
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds


@dataclass
class ReplicationConfig:
    """レプリケーション設定"""
    mode: ReplicationMode = ReplicationMode.ASYNCHRONOUS
    replica_count: int = 2
    replication_timeout_ms: int = 1000
    heartbeat_interval_ms: int = 5000
    max_replication_lag_ms: float = 100.0


class CacheClusterNode:
    """キャッシュクラスタノード"""
    
    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        role: NodeRole = NodeRole.REPLICA
    ):
        """初期化"""
        self.node_info = CacheNode(
            node_id=node_id,
            host=host,
            port=port,
            role=role
        )
        self.cache_data: Dict[str, Any] = {}
        self.replicas: List[str] = []
        self.replication_queue: asyncio.Queue = asyncio.Queue()
    
    async def replicate_to(self, replica_node_id: str, key: str, value: Any) -> bool:
        """レプリカノードにレプリケート"""
        
        try:
            # キューに追加
            await asyncio.wait_for(
                self.replication_queue.put((replica_node_id, key, value)),
                timeout=1.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Replication queue full for {replica_node_id}")
            return False
    
    async def process_replication_queue(self) -> None:
        """レプリケーションキューを処理"""
        
        while True:
            try:
                replica_id, key, value = await self.replication_queue.get()
                # TODO: レプリカノードに送信
                logger.debug(f"Replicating {key} to {replica_id}")
            except Exception as e:
                logger.error(f"Replication error: {e}")


class CacheCluster:
    """キャッシュクラスタ"""
    
    def __init__(self, config: ReplicationConfig = None):
        """初期化"""
        self.config = config or ReplicationConfig()
        self.nodes: Dict[str, CacheClusterNode] = {}
        self.primary_node: Optional[str] = None
        self.replica_nodes: List[str] = []
    
    def add_node(
        self,
        node_id: str,
        host: str,
        port: int,
        role: NodeRole = NodeRole.REPLICA
    ) -> CacheClusterNode:
        """ノードを追加"""
        
        node = CacheClusterNode(node_id, host, port, role)
        self.nodes[node_id] = node
        
        # ロール別にリスト管理
        if role == NodeRole.PRIMARY:
            self.primary_node = node_id
        else:
            self.replica_nodes.append(node_id)
        
        logger.info(f"Added cache node: {node_id} ({role.value})")
        
        return node
    
    def remove_node(self, node_id: str) -> bool:
        """ノードを削除"""
        
        if node_id not in self.nodes:
            return False
        
        # リストから削除
        if node_id == self.primary_node:
            self.primary_node = None
        elif node_id in self.replica_nodes:
            self.replica_nodes.remove(node_id)
        
        del self.nodes[node_id]
        
        logger.info(f"Removed cache node: {node_id}")
        
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """値を取得（プライマリから）"""
        
        if self.primary_node is None:
            return None
        
        primary = self.nodes[self.primary_node]
        return primary.cache_data.get(key)
    
    async def set(self, key: str, value: Any) -> bool:
        """値を設定（プライマリに設定後、レプリカに複製）"""
        
        if self.primary_node is None:
            return False
        
        primary = self.nodes[self.primary_node]
        primary.cache_data[key] = value
        
        # レプリケーション
        async def do_replicate():
            replication_tasks = []
            
            for replica_id in self.replica_nodes:
                if replica_id in self.nodes:
                    task = self.nodes[self.primary_node].replicate_to(
                        replica_id, key, value
                    )
                    replication_tasks.append(task)
            
            # レプリケーションモードに基づいて待機
            if self.config.mode == ReplicationMode.SYNCHRONOUS:
                # 全レプリカの完了を待機
                results = await asyncio.gather(*replication_tasks, return_exceptions=True)
                return all(results)
            elif self.config.mode == ReplicationMode.SEMI_SYNCHRONOUS:
                # 過半数のレプリカ完了を待機
                results = await asyncio.gather(*replication_tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r)
                return success_count >= len(self.replica_nodes) // 2 + 1
            else:  # ASYNCHRONOUS
                # 非同期で実行
                if replication_tasks:
                    await asyncio.gather(*replication_tasks, return_exceptions=True)
                return True
        
        # 非同期モードではバックグラウンドで実行
        if self.config.mode == ReplicationMode.ASYNCHRONOUS:
            asyncio.create_task(do_replicate())
            return True
        else:
            # 同期/準同期は結果を待機
            return await do_replicate()
    
    async def failover(self) -> bool:
        """フェイルオーバー（プライマリ障害時）"""
        
        if self.primary_node is None:
            return False
        
        # プライマリが健全か確認
        primary = self.nodes[self.primary_node]
        
        if not primary.node_info.is_alive:
            logger.warning(f"Primary node {self.primary_node} failed. Starting failover.")
            
            # 新しいプライマリを選択（レプリカから最新のものを選択）
            best_replica = max(
                self.replica_nodes,
                key=lambda r: self.nodes[r].node_info.replicated_entries,
                default=None
            )
            
            if best_replica:
                # ロール変更
                self.nodes[best_replica].node_info.role = NodeRole.PRIMARY
                self.primary_node = best_replica
                self.replica_nodes.remove(best_replica)
                
                logger.info(f"Failover complete. New primary: {best_replica}")
                
                return True
        
        return False
    
    async def check_cluster_health(self) -> Dict[str, Any]:
        """クラスタヘルスチェック"""
        
        health_status = {
            "primary": None,
            "replicas": {},
            "overall_healthy": False
        }
        
        # プライマリヘルスチェック
        if self.primary_node:
            primary = self.nodes[self.primary_node]
            primary.node_info.last_heartbeat = datetime.utcnow()
            
            health_status["primary"] = {
                "node_id": self.primary_node,
                "healthy": primary.node_info.is_healthy,
                "entries": len(primary.cache_data)
            }
        
        # レプリカヘルスチェック
        healthy_replicas = 0
        
        for replica_id in self.replica_nodes:
            if replica_id in self.nodes:
                replica = self.nodes[replica_id]
                replica.node_info.last_heartbeat = datetime.utcnow()
                
                is_healthy = replica.node_info.is_healthy
                
                health_status["replicas"][replica_id] = {
                    "healthy": is_healthy,
                    "replication_lag_ms": replica.node_info.replication_lag_ms,
                    "entries": len(replica.cache_data)
                }
                
                if is_healthy:
                    healthy_replicas += 1
        
        # 全体的なヘルス判定
        primary_healthy = (
            health_status["primary"] and
            health_status["primary"]["healthy"]
        )
        replicas_healthy = healthy_replicas >= self.config.replica_count - 1
        
        health_status["overall_healthy"] = primary_healthy and replicas_healthy
        
        return health_status
    
    def get_report(self) -> Dict[str, Any]:
        """レポート取得"""
        
        report = {
            "replication_mode": self.config.mode.value,
            "replica_count_configured": self.config.replica_count,
            "nodes": {}
        }
        
        # ノード情報
        for node_id, node in self.nodes.items():
            report["nodes"][node_id] = {
                "role": node.node_info.role.value,
                "host": node.node_info.host,
                "port": node.node_info.port,
                "healthy": node.node_info.is_healthy,
                "entries": len(node.cache_data),
                "replication_lag_ms": node.node_info.replication_lag_ms
            }
        
        return report


class CacheConsistencyManager:
    """キャッシュ一貫性管理"""
    
    def __init__(self, cluster: CacheCluster):
        """初期化"""
        self.cluster = cluster
        self.consistency_violations: List[tuple] = []
    
    async def verify_consistency(self) -> bool:
        """一貫性を検証"""
        
        if not self.cluster.primary_node:
            return False
        
        primary = self.cluster.nodes[self.cluster.primary_node]
        
        violations = 0
        
        # 各レプリカとプライマリの比較
        for replica_id in self.cluster.replica_nodes:
            if replica_id not in self.cluster.nodes:
                continue
            
            replica = self.cluster.nodes[replica_id]
            
            # キーセットの比較
            primary_keys = set(primary.cache_data.keys())
            replica_keys = set(replica.cache_data.keys())
            
            # 不一致を検出
            missing_in_replica = primary_keys - replica_keys
            extra_in_replica = replica_keys - primary_keys
            
            if missing_in_replica or extra_in_replica:
                self.consistency_violations.append((
                    replica_id,
                    {
                        "missing": len(missing_in_replica),
                        "extra": len(extra_in_replica)
                    }
                ))
                violations += 1
        
        logger.info(f"Consistency check: {violations} violations detected")
        
        return violations == 0
    
    async def repair_consistency(self) -> int:
        """一貫性を修復"""
        
        if not self.cluster.primary_node:
            return 0
        
        primary = self.cluster.nodes[self.cluster.primary_node]
        repaired = 0
        
        # 各レプリカを修復
        for replica_id in self.cluster.replica_nodes:
            if replica_id not in self.cluster.nodes:
                continue
            
            replica = self.cluster.nodes[replica_id]
            
            # プライマリのすべてのキーをレプリカに複製
            for key, value in primary.cache_data.items():
                if key not in replica.cache_data:
                    replica.cache_data[key] = value
                    repaired += 1
        
        logger.info(f"Repaired {repaired} inconsistent entries")
        
        return repaired
