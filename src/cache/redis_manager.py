"""
Redis キャッシュ管理モジュール

L3 キャッシュ層実装
- マルチテナント対応
- 自動フェイルオーバー
- セキュリティコンテキスト考慮
"""

import redis
from redis.sentinel import Sentinel
from typing import Any, Optional, List, Dict
import json
import logging
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from enum import Enum

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """キャッシュ層の分類"""
    LAYER1_AUTH = "layer1_auth"
    LAYER2_CRYPTO = "layer2_crypto"
    LAYER3_NETWORK = "layer3_network"
    LAYER4_SOC = "layer4_soc"
    LAYER5_ML = "layer5_ml"
    LAYER6_COMPLIANCE = "layer6_compliance"
    LAYER7_GLOBAL = "layer7_global"


class CacheConfig:
    """Redis キャッシュ設定"""
    
    # Sentinel 設定
    SENTINEL_HOSTS = [
        ("redis-sentinel-1", 26379),
        ("redis-sentinel-2", 26380),
        ("redis-sentinel-3", 26381),
    ]
    SENTINEL_SERVICE_NAME = "esp-redis"
    
    # Redis 設定
    SOCKET_TIMEOUT = 2
    SOCKET_CONNECT_TIMEOUT = 2
    RETRY_ON_TIMEOUT = True
    
    # TTL 設定 (秒)
    TTL_DEFAULTS = {
        CacheTier.LAYER1_AUTH: 300,              # 5 分
        CacheTier.LAYER2_CRYPTO: 3600,           # 1 時間
        CacheTier.LAYER3_NETWORK: 3600,          # 1 時間
        CacheTier.LAYER4_SOC: 1800,              # 30 分
        CacheTier.LAYER5_ML: 900,                # 15 分
        CacheTier.LAYER6_COMPLIANCE: 600,        # 10 分
        CacheTier.LAYER7_GLOBAL: 3600,           # 1 時間
    }
    
    # メモリ設定
    MAX_MEMORY = "2gb"
    MAX_MEMORY_POLICY = "allkeys-lru"
    
    # パフォーマンス目標
    TARGET_HIT_RATIO = 0.85
    MAX_LOOKUP_LATENCY_MS = 5


class CacheKeyGenerator:
    """キャッシュキー生成ロジック"""
    
    @staticmethod
    def build_key(
        tier: CacheTier,
        entity_type: str,
        entity_id: str,
        tenant_id: Optional[str] = None,
        context: Optional[str] = None,
        version: int = 1
    ) -> str:
        """
        キャッシュキーを生成
        
        Format: <tier>:<entity_type>:<entity_id>[:<tenant_id>][:<context>]:v<version>
        """
        parts = [
            tier.value,
            entity_type,
            entity_id,
        ]
        
        if tenant_id:
            parts.append(tenant_id)
        
        if context:
            parts.append(context)
        
        key = ":".join(parts)
        return f"{key}:v{version}"
    
    # === Layer 1: Authentication ===
    @staticmethod
    def auth_session(session_id: str, tenant_id: str) -> str:
        """認証セッションキー"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER1_AUTH,
            "session",
            session_id,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def user_permissions(user_id: str, tenant_id: str) -> str:
        """ユーザー権限キー"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER1_AUTH,
            "permissions",
            user_id,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def user_roles(user_id: str, tenant_id: str) -> str:
        """ユーザーロールキー"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER1_AUTH,
            "roles",
            user_id,
            tenant_id=tenant_id
        )
    
    # === Layer 2: Encryption ===
    @staticmethod
    def encryption_key_meta(key_id: str, tenant_id: str) -> str:
        """暗号化キーメタデータ"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER2_CRYPTO,
            "key_meta",
            key_id,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def key_mapping(entity_type: str, entity_id: str) -> str:
        """キーマッピング（エンティティ → キーID）"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER2_CRYPTO,
            "key_mapping",
            f"{entity_type}:{entity_id}"
        )
    
    # === Layer 3: Network ===
    @staticmethod
    def network_policy(policy_id: str, tenant_id: str) -> str:
        """ネットワークポリシー"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER3_NETWORK,
            "policy",
            policy_id,
            tenant_id=tenant_id
        )
    
    # === Layer 4: SOC ===
    @staticmethod
    def threat_alert(alert_id: str) -> str:
        """脅威アラート"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER4_SOC,
            "alert",
            alert_id
        )
    
    @staticmethod
    def threat_intelligence(threat_id: str) -> str:
        """脅威インテリジェンス"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER4_SOC,
            "threat",
            threat_id
        )
    
    # === Layer 5: ML ===
    @staticmethod
    def threat_score(user_id: str, session_id: str) -> str:
        """脅威スコア"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER5_ML,
            "threat_score",
            f"{user_id}:{session_id}",
            context="realtime"
        )
    
    @staticmethod
    def ml_model_meta(model_name: str, version: str) -> str:
        """ML モデルメタデータ"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER5_ML,
            "model",
            model_name,
            context=version,
            version=1
        )
    
    # === Layer 6: Compliance ===
    @staticmethod
    def compliance_status(entity_type: str, entity_id: str) -> str:
        """コンプライアンス状態"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER6_COMPLIANCE,
            "status",
            f"{entity_type}:{entity_id}"
        )
    
    @staticmethod
    def compliance_report(report_id: str) -> str:
        """コンプライアンスレポート"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER6_COMPLIANCE,
            "report",
            report_id
        )
    
    # === Layer 7: Global ===
    @staticmethod
    def global_config(config_key: str) -> str:
        """グローバル設定"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER7_GLOBAL,
            "config",
            config_key
        )
    
    @staticmethod
    def tenant_info(tenant_id: str) -> str:
        """テナント情報"""
        return CacheKeyGenerator.build_key(
            CacheTier.LAYER7_GLOBAL,
            "tenant",
            tenant_id
        )


class RedisConnectionManager:
    """
    Redis への安全で効率的なアクセスを提供
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.sentinel = None
        self.master = None
        self.slave = None
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
        }
    
    async def initialize(self):
        """Redis への接続を初期化"""
        try:
            self.sentinel = Sentinel(
                self.config.SENTINEL_HOSTS,
                socket_timeout=self.config.SOCKET_TIMEOUT,
                socket_connect_timeout=self.config.SOCKET_CONNECT_TIMEOUT,
            )
            
            # Master への読み書きアクセス
            self.master = self.sentinel.master_for(
                self.config.SENTINEL_SERVICE_NAME,
                socket_timeout=self.config.SOCKET_TIMEOUT,
            )
            
            # Slave への読み取りアクセス（負荷分散）
            self.slave = self.sentinel.slave_for(
                self.config.SENTINEL_SERVICE_NAME,
                socket_timeout=self.config.SOCKET_TIMEOUT,
            )
            
            # 接続テスト
            self.master.ping()
            self.slave.ping()
            
            logger.info("✅ Redis connection initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """
        キャッシュから値を取得
        
        Args:
            key: キャッシュキー
        
        Returns:
            キャッシュされた値、またはNone
        """
        try:
            value = self.slave.get(key)
            
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            else:
                self._stats["misses"] += 1
                return None
                
        except Exception as e:
            logger.warning(f"⚠️  Cache GET failed: {key} - {e}")
            self._stats["errors"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        tier: CacheTier = CacheTier.LAYER7_GLOBAL,
        ttl: Optional[int] = None
    ) -> bool:
        """
        キャッシュに値を設定
        
        Args:
            key: キャッシュキー
            value: キャッシュ値
            tier: キャッシュ層（TTL決定用）
            ttl: 有効期限（秒）。指定なしの場合は tier デフォルト使用
        
        Returns:
            成功時 True、失敗時 False
        """
        try:
            if ttl is None:
                ttl = self.config.TTL_DEFAULTS.get(tier, 3600)
            
            serialized = json.dumps(value)
            self.master.setex(key, ttl, serialized)
            
            logger.debug(f"✓ Cache SET: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Cache SET failed: {key} - {e}")
            self._stats["errors"] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """キャッシュキーを削除"""
        try:
            self.master.delete(key)
            logger.debug(f"✓ Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Cache DELETE failed: {key} - {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """パターンマッチするキーを一括削除"""
        try:
            keys = self.master.keys(pattern)
            if keys:
                deleted = self.master.delete(*keys)
                logger.info(f"✓ Deleted {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"⚠️  Pattern delete failed: {pattern} - {e}")
            return 0
    
    def get_stats(self) -> Dict[str, int]:
        """キャッシュ統計情報を取得"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_ratio = (
            self._stats["hits"] / total 
            if total > 0 
            else 0.0
        )
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "errors": self._stats["errors"],
            "total": total,
            "hit_ratio": hit_ratio,
            "hit_ratio_percent": f"{hit_ratio * 100:.2f}%",
        }
    
    async def flush_all(self):
        """全キャッシュをクリア（開発用）"""
        try:
            self.master.flushdb()
            logger.warning("⚠️  Cache FLUSHALL executed")
        except Exception as e:
            logger.error(f"❌ FLUSHALL failed: {e}")
    
    async def close(self):
        """接続をクローズ"""
        if self.master:
            self.master.close()
        if self.slave:
            self.slave.close()
        logger.info("Redis connection closed")


class CacheInvalidationEventSystem:
    """イベントベースのキャッシュ無効化システム"""
    
    def __init__(self, redis_manager: RedisConnectionManager):
        self.redis = redis_manager
        self.handlers: Dict[str, List[Any]] = {}
    
    def register_handler(self, event_type: str, handler):
        """イベントハンドラを登録"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"Handler registered: {event_type}")
    
    async def emit(self, event_type: str, **kwargs):
        """イベントを発火して、登録されたハンドラを実行"""
        if event_type in self.handlers:
            logger.debug(f"Event emitted: {event_type} with {kwargs}")
            
            tasks = [
                handler(**kwargs)
                for handler in self.handlers[event_type]
            ]
            
            await asyncio.gather(*tasks)
    
    async def on_user_permission_changed(self, user_id: str, tenant_id: str):
        """ユーザー権限変更時のキャッシュ無効化"""
        logger.info(f"Invalidating permissions cache for user {user_id}")
        
        key = CacheKeyGenerator.user_permissions(user_id, tenant_id)
        await self.redis.delete(key)
    
    async def on_tenant_config_updated(self, tenant_id: str):
        """テナント設定変更時のキャッシュ無効化"""
        logger.info(f"Invalidating tenant config cache for {tenant_id}")
        
        patterns = [
            f"layer1_auth:*:*:{tenant_id}:*",
            f"layer3_network:*:*:{tenant_id}:*",
            f"layer7_global:config:*:*",
        ]
        
        for pattern in patterns:
            await self.redis.delete_pattern(pattern)
    
    async def on_encryption_key_rotated(self, key_id: str, tenant_id: str):
        """暗号化キーローテーション時のキャッシュ無効化"""
        logger.info(f"Invalidating encryption key cache for key {key_id}")
        
        key = CacheKeyGenerator.encryption_key_meta(key_id, tenant_id)
        await self.redis.delete(key)
        
        # キーマッピングもクリア
        pattern = f"layer2_crypto:key_mapping:*"
        await self.redis.delete_pattern(pattern)
    
    async def on_threat_level_changed(self, user_id: str):
        """脅威レベル変更時のキャッシュ無効化"""
        logger.info(f"Invalidating threat score cache for user {user_id}")
        
        pattern = f"layer5_ml:threat_score:{user_id}:*"
        await self.redis.delete_pattern(pattern)


# グローバルインスタンス
_cache_manager: Optional[RedisConnectionManager] = None
_invalidation_system: Optional[CacheInvalidationEventSystem] = None


async def initialize_cache():
    """キャッシュシステムを初期化"""
    global _cache_manager, _invalidation_system
    
    _cache_manager = RedisConnectionManager()
    await _cache_manager.initialize()
    
    _invalidation_system = CacheInvalidationEventSystem(_cache_manager)
    
    logger.info("✅ Cache system initialized")


def get_cache_manager() -> RedisConnectionManager:
    """キャッシュマネージャを取得"""
    if _cache_manager is None:
        raise RuntimeError("Cache system not initialized. Call initialize_cache() first.")
    return _cache_manager


def get_invalidation_system() -> CacheInvalidationEventSystem:
    """キャッシュ無効化システムを取得"""
    if _invalidation_system is None:
        raise RuntimeError("Cache invalidation system not initialized.")
    return _invalidation_system
