import os
import json
import logging
from typing import Any, Optional
import redis
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CacheOptimizer:
    """
    Phase 19 Task 3: パフォーマンス最適化
    L1 (Memory) および L2 (Redis) キャッシュを管理するクラス。
    """

    def __init__(self):
        load_dotenv()
        self.enabled = os.getenv("RAG_CACHE_ENABLED", "true").lower() == "true"
        self.ttl = int(os.getenv("RAG_CACHE_TTL", "3600"))
        
        # Redis接続
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        self.redis_client = None
        if self.enabled:
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    socket_timeout=2
                )
                # 接続テスト
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. L2 Cache will be disabled.")
                self.redis_client = None

    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """キャッシュから値を取得する。"""
        if not self.enabled:
            return None
            
        full_key = f"rag:{namespace}:{key}"
        
        # 1. L1 Cache (Memory) - 実際には上位レイヤーでLRU等が効くが、ここではL2取得を主眼に置く
        # 2. L2 Cache (Redis)
        if self.redis_client:
            try:
                val = self.redis_client.get(full_key)
                if val:
                    logger.debug(f"Cache Hit (L2): {full_key}")
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        return None

    def set(self, key: str, value: Any, namespace: str = "default", ttl: Optional[int] = None) -> bool:
        """キャッシュに値を設定する。"""
        if not self.enabled:
            return False
            
        full_key = f"rag:{namespace}:{key}"
        expiry = ttl if ttl is not None else self.ttl
        
        if self.redis_client:
            try:
                self.redis_client.set(
                    full_key,
                    json.dumps(value, ensure_ascii=False),
                    ex=expiry
                )
                logger.debug(f"Cache Set (L2): {full_key} (ttl={expiry})")
                return True
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
        
        return False

    def delete(self, key: str, namespace: str = "default") -> bool:
        """キャッシュを削除する。"""
        if not self.redis_client:
            return False
        
        full_key = f"rag:{namespace}:{key}"
        try:
            return bool(self.redis_client.delete(full_key))
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False

    def clear_namespace(self, namespace: str) -> int:
        """特定のネームスペースのキャッシュをすべて削除する。"""
        if not self.redis_client:
            return 0
            
        pattern = f"rag:{namespace}:*"
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")
            return 0

# シングルトンインスタンスの提供
_instance = None

def get_cache_optimizer() -> CacheOptimizer:
    global _instance
    if _instance is None:
        _instance = CacheOptimizer()
    return _instance
