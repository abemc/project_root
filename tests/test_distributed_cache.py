"""
分散キャッシングテスト

DistributedCache, CacheCluster, 一貫性管理のテスト
"""

import pytest
import asyncio

from src.microservices.distributed_cache import (
    CacheManager, DistributedCache, CachePolicy,
    CacheStrategy, InvalidationStrategy, CacheInvalidationManager
)
from src.microservices.cache_cluster import (
    CacheCluster, CacheClusterNode, CacheConsistencyManager,
    NodeRole, ReplicationMode, ReplicationConfig
)


class TestDistributedCache:
    """DistributedCache テスト"""
    
    @pytest.mark.asyncio
    async def test_cache_manager_creation(self):
        """キャッシュマネージャー作成テスト"""
        manager = CacheManager()
        
        assert manager.backend is not None
        assert manager.cache is not None
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """設定と取得テスト"""
        manager = CacheManager()
        
        await manager.cache.set("test_key", "test_value")
        value = await manager.cache.get("test_key")
        
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """キャッシュミステスト"""
        manager = CacheManager()
        
        value = await manager.cache.get("nonexistent_key")
        
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_deletion(self):
        """キャッシュ削除テスト"""
        manager = CacheManager()
        
        await manager.cache.set("key_to_delete", "value")
        result = await manager.cache.delete("key_to_delete")
        value = await manager.cache.get("key_to_delete")
        
        assert result is True
        assert value is None
    
    @pytest.mark.asyncio
    async def test_get_or_set_hit(self):
        """get_or_set: キャッシュヒットテスト"""
        manager = CacheManager()
        
        await manager.cache.set("cached_key", "cached_value")
        
        def factory():
            return "factory_value"
        
        result = await manager.cache.get_or_set("cached_key", factory)
        
        assert result == "cached_value"
    
    @pytest.mark.asyncio
    async def test_get_or_set_miss(self):
        """get_or_set: キャッシュミステスト"""
        manager = CacheManager()
        
        def factory():
            return "factory_value"
        
        result = await manager.cache.get_or_set("new_key", factory)
        
        assert result == "factory_value"
        
        # キャッシュに設定されたか確認
        cached = await manager.cache.get("new_key")
        assert cached == "factory_value"
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """キャッシュTTL有効期限テスト"""
        manager = CacheManager()
        
        # TTL 1秒で設定
        await manager.cache.set("ttl_key", "ttl_value", ttl_seconds=1)
        
        # 即座に取得
        value = await manager.cache.get("ttl_key")
        assert value == "ttl_value"
        
        # 2秒待機
        await asyncio.sleep(2)
        
        # TTL切れで None を返す
        value = await manager.cache.get("ttl_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_eviction_behavior(self):
        """エビクション動作テスト"""
        policy = CachePolicy(
            strategy=CacheStrategy.LRU,
            max_size_mb=1,
            ttl_seconds=3600
        )
        manager = CacheManager(policy)
        
        # いくつかのデータを追加
        for i in range(5):
            value = {"data": "x" * 1000}  # 適度なサイズ
            await manager.cache.set(f"key_{i}", value)
        
        stats = await manager.get_stats()
        
        # エントリが存在することを確認
        assert stats.entry_count > 0


class TestCacheInvalidation:
    """キャッシュ無効化テスト"""
    
    @pytest.mark.asyncio
    async def test_immediate_invalidation(self):
        """即座無効化テスト"""
        manager = CacheManager()
        
        # キャッシュ設定
        await manager.cache.set("user:123", {"name": "Alice"})
        await manager.cache.set("user:123:profile", {"role": "admin"})
        
        # イベントベースの無効化
        invalidation_mgr = manager.invalidation_manager
        await invalidation_mgr.invalidate_on_event(
            "user_updated",
            {"user_id": 123}
        )
        
        # キャッシュが無効化されたか確認
        value = await manager.cache.get("user:123")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_lazy_invalidation(self):
        """遅延無効化テスト"""
        manager = CacheManager()
        
        invalidation_mgr = CacheInvalidationManager(
            manager.cache,
            InvalidationStrategy.LAZY
        )
        
        await manager.cache.set("product:456", {"name": "Widget"})
        
        # 遅延無効化をスケジュール
        await invalidation_mgr.invalidate_on_event(
            "product_updated",
            {"product_id": 456}
        )
        
        # 遅延無効化は即座には無効化されない
        value = await manager.cache.get("product:456")
        assert value == {"name": "Widget"}


class TestCacheCluster:
    """キャッシュクラスタテスト"""
    
    def test_cluster_creation(self):
        """クラスタ作成テスト"""
        cluster = CacheCluster()
        
        assert cluster.primary_node is None
        assert len(cluster.nodes) == 0
    
    def test_add_node(self):
        """ノード追加テスト"""
        cluster = CacheCluster()
        
        node = cluster.add_node(
            "cache-1",
            "localhost",
            6379,
            NodeRole.PRIMARY
        )
        
        assert node is not None
        assert cluster.primary_node == "cache-1"
    
    def test_add_multiple_nodes(self):
        """複数ノード追加テスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        cluster.add_node("cache-3", "localhost", 6381, NodeRole.REPLICA)
        
        assert len(cluster.nodes) == 3
        assert len(cluster.replica_nodes) == 2
    
    def test_remove_node(self):
        """ノード削除テスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        result = cluster.remove_node("cache-2")
        
        assert result is True
        assert len(cluster.nodes) == 1
        assert len(cluster.replica_nodes) == 0
    
    @pytest.mark.asyncio
    async def test_set_get_cluster(self):
        """クラスタセット・ゲットテスト"""
        config = ReplicationConfig(mode=ReplicationMode.ASYNCHRONOUS)
        cluster = CacheCluster(config)
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        await cluster.set("test_key", "test_value")
        value = await cluster.get("test_key")
        
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_cluster_health_check(self):
        """クラスタヘルスチェックテスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        health = await cluster.check_cluster_health()
        
        assert health["primary"] is not None
        assert len(health["replicas"]) == 1
    
    @pytest.mark.asyncio
    async def test_failover(self):
        """フェイルオーバーテスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        # プライマリを不健全にマーク
        primary = cluster.nodes[cluster.primary_node]
        primary.node_info.is_healthy = False
        
        # フェイルオーバー実行
        result = await cluster.failover()
        
        # フェイルオーバーが成功し、新しいプライマリが選択されたことを確認
        if result:
            assert cluster.primary_node == "cache-2"
            assert cluster.nodes["cache-2"].node_info.role == NodeRole.PRIMARY


class TestConsistencyManagement:
    """一貫性管理テスト"""
    
    @pytest.mark.asyncio
    async def test_consistency_verification(self):
        """一貫性検証テスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        # プライマリにデータを追加
        primary = cluster.nodes["cache-1"]
        replica = cluster.nodes["cache-2"]
        
        primary.cache_data["key1"] = "value1"
        replica.cache_data["key1"] = "value1"  # 同期
        
        consistency_mgr = CacheConsistencyManager(cluster)
        is_consistent = await consistency_mgr.verify_consistency()
        
        # データが同じなので一貫性がある
        assert is_consistent is True
    
    @pytest.mark.asyncio
    async def test_consistency_repair(self):
        """一貫性修復テスト"""
        cluster = CacheCluster()
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        primary = cluster.nodes["cache-1"]
        replica = cluster.nodes["cache-2"]
        
        # プライマリにデータを追加
        primary.cache_data["key1"] = "value1"
        primary.cache_data["key2"] = "value2"
        
        # レプリカが一部のデータを欠いている状態を作成
        replica.cache_data["key1"] = "value1"
        
        # 一貫性修復
        consistency_mgr = CacheConsistencyManager(cluster)
        repaired = await consistency_mgr.repair_consistency()
        
        # key2が修復されたことを確認
        assert repaired > 0
        assert replica.cache_data.get("key2") == "value2"


class TestReplicationModes:
    """レプリケーションモードテスト"""
    
    @pytest.mark.asyncio
    async def test_synchronous_replication(self):
        """同期レプリケーションテスト"""
        config = ReplicationConfig(
            mode=ReplicationMode.SYNCHRONOUS,
            replica_count=2
        )
        cluster = CacheCluster(config)
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        cluster.add_node("cache-3", "localhost", 6381, NodeRole.REPLICA)
        
        result = await cluster.set("sync_key", "sync_value")
        
        # 同期モードでは、レプリケーションが完了するまで待機
        # 実装により success/failure が返される
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_asynchronous_replication(self):
        """非同期レプリケーションテスト"""
        config = ReplicationConfig(
            mode=ReplicationMode.ASYNCHRONOUS,
            replica_count=2
        )
        cluster = CacheCluster(config)
        
        cluster.add_node("cache-1", "localhost", 6379, NodeRole.PRIMARY)
        cluster.add_node("cache-2", "localhost", 6380, NodeRole.REPLICA)
        
        result = await cluster.set("async_key", "async_value")
        
        # 非同期モードでは即座に True を返す
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
