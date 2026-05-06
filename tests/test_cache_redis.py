"""
Redis キャッシュシステムのテストコード

Unit テスト・統合テスト・パフォーマンステスト
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.cache.redis_manager import (
    RedisConnectionManager,
    CacheKeyGenerator,
    CacheTier,
    CacheConfig,
    CacheInvalidationEventSystem,
)


class TestCacheKeyGenerator:
    """キャッシュキー生成ロジックのテスト"""
    
    def test_auth_session_key_generation(self):
        """認証セッションキー生成テスト"""
        key = CacheKeyGenerator.auth_session("sess_123", "tenant_456")
        
        assert "layer1_auth" in key
        assert "session" in key
        assert "sess_123" in key
        assert "tenant_456" in key
        assert ":v1" in key
    
    def test_user_permissions_key_generation(self):
        """ユーザー権限キー生成テスト"""
        key = CacheKeyGenerator.user_permissions("user_789", "tenant_456")
        
        assert "layer1_auth" in key
        assert "permissions" in key
        assert "user_789" in key
        assert "tenant_456" in key
    
    def test_encryption_key_meta_generation(self):
        """暗号化キーメタキー生成テスト"""
        key = CacheKeyGenerator.encryption_key_meta("key_111", "tenant_456")
        
        assert "layer2_crypto" in key
        assert "key_meta" in key
        assert "key_111" in key
    
    def test_threat_score_key_generation(self):
        """脅威スコアキー生成テスト"""
        key = CacheKeyGenerator.threat_score("user_789", "session_999")
        
        assert "layer5_ml" in key
        assert "threat_score" in key
        assert "realtime" in key
    
    def test_key_uniqueness(self):
        """異なる入力で異なるキーが生成される"""
        key1 = CacheKeyGenerator.auth_session("sess_1", "tenant_1")
        key2 = CacheKeyGenerator.auth_session("sess_2", "tenant_1")
        
        assert key1 != key2
    
    def test_key_consistency(self):
        """同じ入力で同じキーが生成される"""
        key1 = CacheKeyGenerator.auth_session("sess_123", "tenant_456")
        key2 = CacheKeyGenerator.auth_session("sess_123", "tenant_456")
        
        assert key1 == key2


class TestRedisConnectionManager:
    """Redis 接続マネージャーのテスト"""
    
    @pytest.mark.asyncio
    async def test_cache_get_hit(self):
        """キャッシュヒット時のテスト"""
        manager = RedisConnectionManager()
        
        # モック Redis クライアント
        mock_slave = Mock()
        test_data = {"user_id": "123", "role": "admin"}
        mock_slave.get.return_value = json.dumps(test_data)
        
        manager.slave = mock_slave
        
        result = await manager.get("test_key")
        
        assert result == test_data
        assert manager._stats["hits"] == 1
        mock_slave.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_get_miss(self):
        """キャッシュミス時のテスト"""
        manager = RedisConnectionManager()
        
        mock_slave = Mock()
        mock_slave.get.return_value = None
        
        manager.slave = mock_slave
        
        result = await manager.get("nonexistent_key")
        
        assert result is None
        assert manager._stats["misses"] == 1
    
    @pytest.mark.asyncio
    async def test_cache_set(self):
        """キャッシュ設定テスト"""
        manager = RedisConnectionManager()
        
        mock_master = Mock()
        manager.master = mock_master
        
        test_data = {"user_id": "123", "permissions": ["read", "write"]}
        
        result = await manager.set(
            "test_key",
            test_data,
            tier=CacheTier.LAYER1_AUTH
        )
        
        assert result is True
        mock_master.setex.assert_called_once()
        
        # 引数の確認
        call_args = mock_master.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 300  # Layer1 Auth の TTL
        assert json.loads(call_args[0][2]) == test_data
    
    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """キャッシュ削除テスト"""
        manager = RedisConnectionManager()
        
        mock_master = Mock()
        manager.master = mock_master
        
        result = await manager.delete("test_key")
        
        assert result is True
        mock_master.delete.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_delete_pattern(self):
        """パターン削除テスト"""
        manager = RedisConnectionManager()
        
        mock_master = Mock()
        mock_master.keys.return_value = [
            "layer1_auth:permissions:user1:tenant1:v1",
            "layer1_auth:permissions:user2:tenant1:v1",
            "layer1_auth:permissions:user3:tenant1:v1",
        ]
        mock_master.delete.return_value = 3
        
        manager.master = mock_master
        
        deleted_count = await manager.delete_pattern(
            "layer1_auth:permissions:*:tenant1:*"
        )
        
        assert deleted_count == 3
    
    def test_cache_stats(self):
        """キャッシュ統計テスト"""
        manager = RedisConnectionManager()
        
        manager._stats = {
            "hits": 80,
            "misses": 20,
            "errors": 1,
        }
        
        stats = manager.get_stats()
        
        assert stats["hits"] == 80
        assert stats["misses"] == 20
        assert stats["errors"] == 1
        assert stats["total"] == 100
        assert abs(stats["hit_ratio"] - 0.8) < 0.01


class TestCacheInvalidationEventSystem:
    """キャッシュ無効化イベントシステムのテスト"""
    
    @pytest.mark.asyncio
    async def test_event_handler_registration(self):
        """イベントハンドラ登録テスト"""
        mock_manager = Mock(spec=RedisConnectionManager)
        system = CacheInvalidationEventSystem(mock_manager)
        
        handler = AsyncMock()
        system.register_handler("user_permission_changed", handler)
        
        assert "user_permission_changed" in system.handlers
        assert len(system.handlers["user_permission_changed"]) == 1
    
    @pytest.mark.asyncio
    async def test_event_emission(self):
        """イベント発火テスト"""
        mock_manager = Mock(spec=RedisConnectionManager)
        system = CacheInvalidationEventSystem(mock_manager)
        
        handler = AsyncMock()
        system.register_handler("test_event", handler)
        
        await system.emit("test_event", param1="value1", param2="value2")
        
        handler.assert_called_once_with(param1="value1", param2="value2")
    
    @pytest.mark.asyncio
    async def test_user_permission_invalidation(self):
        """ユーザー権限無効化テスト"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.delete = AsyncMock()
        
        system = CacheInvalidationEventSystem(mock_manager)
        
        await system.on_user_permission_changed("user_123", "tenant_456")
        
        mock_manager.delete.assert_called_once()
        call_args = mock_manager.delete.call_args[0][0]
        assert "layer1_auth" in call_args
        assert "permissions" in call_args


class TestCachePerformance:
    """キャッシュパフォーマンステスト"""
    
    @pytest.mark.asyncio
    async def test_cache_lookup_speed(self):
        """キャッシュルックアップ速度テスト"""
        manager = RedisConnectionManager()
        
        mock_slave = Mock()
        mock_slave.get.return_value = json.dumps({"data": "test"})
        manager.slave = mock_slave
        
        start_time = time.time()
        
        # 1000回のキャッシュ参照
        for i in range(1000):
            await manager.get(f"key_{i}")
        
        elapsed_time = time.time() - start_time
        avg_latency_ms = (elapsed_time / 1000) * 1000
        
        # 目標: 平均 5ms 以下
        assert avg_latency_ms < 5, f"Latency too high: {avg_latency_ms}ms"
    
    def test_cache_hit_ratio_calculation(self):
        """キャッシュヒット率計算テスト"""
        manager = RedisConnectionManager()
        
        # 85% ヒット率をシミュレート
        manager._stats = {
            "hits": 850,
            "misses": 150,
            "errors": 0,
        }
        
        stats = manager.get_stats()
        
        assert abs(stats["hit_ratio"] - 0.85) < 0.001
        assert "85.0" in stats["hit_ratio_percent"]
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """並行キャッシュアクセステスト"""
        manager = RedisConnectionManager()
        
        mock_slave = Mock()
        mock_slave.get.return_value = json.dumps({"data": "test"})
        manager.slave = mock_slave
        
        # 100 個の並行リクエスト
        tasks = [
            manager.get(f"key_{i % 10}")  # キーは 10 個のみ
            for i in range(100)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # すべてのリクエストが成功
        assert len(results) == 100
        assert all(result == {"data": "test"} for result in results)


class TestCacheIntegration:
    """統合テスト"""
    
    @pytest.mark.asyncio
    async def test_full_cache_workflow(self):
        """フルキャッシュワークフローテスト"""
        manager = RedisConnectionManager()
        
        mock_slave = Mock()
        mock_master = Mock()
        manager.slave = mock_slave
        manager.master = mock_master
        
        # Step 1: キャッシュミス → DB アクセス
        mock_slave.get.return_value = None
        
        key = CacheKeyGenerator.user_permissions("user_123", "tenant_456")
        result = await manager.get(key)
        
        assert result is None
        assert manager._stats["misses"] == 1
        
        # Step 2: DB から取得したデータをキャッシュに設定
        db_data = {"user_id": "user_123", "permissions": ["read", "write", "admin"]}
        success = await manager.set(key, db_data, tier=CacheTier.LAYER1_AUTH)
        
        assert success is True
        
        # Step 3: キャッシュヒット
        mock_slave.get.return_value = json.dumps(db_data)
        cached_result = await manager.get(key)
        
        assert cached_result == db_data
        assert manager._stats["hits"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
