"""
分散キャッシング

複数のマイクロサービスインスタンス間でのキャッシュ共有を実現
Redis/Memcached バックエンド対応
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List, Callable
import json
import logging
import asyncio
from functools import wraps


logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """キャッシング戦略"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


class InvalidationStrategy(Enum):
    """キャッシュ無効化戦略"""
    IMMEDIATE = "immediate"  # 即座に無効化
    LAZY = "lazy"  # 遅延無効化（アクセス時）
    TIME_BASED = "time_based"  # 時間ベース
    EVENT_BASED = "event_based"  # イベントベース


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    ttl_seconds: Optional[int] = None
    access_count: int = 0
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """有効期限切れ判定"""
        if self.ttl_seconds is None:
            return False
        
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """エントリの年齢"""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    @property
    def recency_seconds(self) -> float:
        """最後のアクセスからの経過時間"""
        return (datetime.utcnow() - self.last_accessed).total_seconds()


@dataclass
class CachePolicy:
    """キャッシュポリシー"""
    strategy: CacheStrategy = CacheStrategy.LRU
    max_size_mb: int = 100
    ttl_seconds: int = 3600
    eviction_ratio: float = 0.2  # サイズ超過時の削除比率
    enable_compression: bool = False


@dataclass
class CacheStats:
    """キャッシュ統計"""
    total_hits: int = 0
    total_misses: int = 0
    total_evictions: int = 0
    total_invalidations: int = 0
    current_size_mb: float = 0.0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """ヒット率"""
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return (self.total_hits / total) * 100


class CacheBackendBase(ABC):
    """キャッシュバックエンド基本クラス"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """値を設定"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """値を削除"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """キーが存在するか確認"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """全キャッシュをクリア"""
        pass


class InMemoryCache(CacheBackendBase):
    """インメモリキャッシュバックエンド"""
    
    def __init__(self, policy: CachePolicy):
        """初期化"""
        self.policy = policy
        self.cache: Dict[str, CacheEntry] = {}
        self.stats = CacheStats()
    
    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        
        if key not in self.cache:
            self.stats.total_misses += 1
            return None
        
        entry = self.cache[key]
        
        # 有効期限切れ確認
        if entry.is_expired:
            await self.delete(key)
            self.stats.total_misses += 1
            return None
        
        # アクセス情報更新
        entry.last_accessed = datetime.utcnow()
        entry.access_count += 1
        
        self.stats.total_hits += 1
        return entry.value
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """値を設定"""
        
        # デフォルトTTL
        if ttl_seconds is None:
            ttl_seconds = self.policy.ttl_seconds
        
        # サイズ計算（文字列化してバイト数を計算）
        try:
            size_bytes = len(json.dumps(value, default=str).encode())
        except Exception:
            size_bytes = 1000  # フォールバック
        
        # 現在のサイズ計算
        current_size = sum(e.size_bytes for e in self.cache.values())
        max_size_bytes = self.policy.max_size_mb * 1024 * 1024
        
        # サイズ超過時のエビクション
        if current_size + size_bytes > max_size_bytes:
            # 削除対象のサイズを計算
            size_to_free = current_size + size_bytes - int(max_size_bytes * 0.8)
            await self._evict_entries(size_to_free)
        
        # エントリを作成・更新
        now = datetime.utcnow()
        self.cache[key] = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            last_accessed=now,
            ttl_seconds=ttl_seconds,
            size_bytes=size_bytes
        )
        
        # 統計更新
        self._update_stats()
        
        return True
    
    async def delete(self, key: str) -> bool:
        """値を削除"""
        
        if key in self.cache:
            del self.cache[key]
            self.stats.total_invalidations += 1
            self._update_stats()
            return True
        
        return False
    
    async def exists(self, key: str) -> bool:
        """キーが存在するか確認"""
        
        if key not in self.cache:
            return False
        
        entry = self.cache[key]
        return not entry.is_expired
    
    async def clear(self) -> bool:
        """全キャッシュをクリア"""
        
        self.cache.clear()
        self._update_stats()
        return True
    
    async def _evict_entries(self, size_to_free: int) -> None:
        """エントリをエビクト"""
        
        # エビクション対象エントリを選択
        entries_to_evict = self._select_entries_for_eviction(size_to_free)
        
        for entry in entries_to_evict:
            del self.cache[entry.key]
            self.stats.total_evictions += 1
    
    def _select_entries_for_eviction(self, size_to_free: int) -> List[CacheEntry]:
        """エビクト対象エントリを選択"""
        
        entries = list(self.cache.values())
        freed = 0
        result = []
        
        # 戦略に基づいてソート
        if self.policy.strategy == CacheStrategy.LRU:
            entries.sort(key=lambda e: e.recency_seconds, reverse=True)
        elif self.policy.strategy == CacheStrategy.LFU:
            entries.sort(key=lambda e: e.access_count)
        elif self.policy.strategy == CacheStrategy.FIFO:
            entries.sort(key=lambda e: e.created_at)
        elif self.policy.strategy == CacheStrategy.TTL:
            entries.sort(key=lambda e: e.age_seconds, reverse=True)
        
        for entry in entries:
            if freed >= size_to_free:
                break
            result.append(entry)
            freed += entry.size_bytes
        
        return result
    
    def _update_stats(self) -> None:
        """統計を更新"""
        
        self.stats.entry_count = len(self.cache)
        self.stats.current_size_mb = sum(
            e.size_bytes for e in self.cache.values()
        ) / (1024 * 1024)


class DistributedCache:
    """分散キャッシュ管理"""
    
    def __init__(self, backend: CacheBackendBase):
        """初期化"""
        self.backend = backend
        self.invalidation_listeners: List[Callable] = []
    
    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        return await self.backend.get(key)
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """値を設定"""
        return await self.backend.set(key, value, ttl_seconds)
    
    async def delete(self, key: str) -> bool:
        """値を削除"""
        return await self.backend.delete(key)
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """キャッシュから取得、無い場合は生成して設定"""
        
        # キャッシュから取得
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # キャッシュに無い場合は生成
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, value, ttl_seconds)
        
        return value
    
    async def invalidate(self, pattern: str) -> int:
        """パターンマッチでキャッシュを無効化"""
        
        count = 0
        # TODO: パターンマッチ実装
        
        # リスナーに通知
        for listener in self.invalidation_listeners:
            await listener(pattern)
        
        return count
    
    def on_invalidation(self, callback: Callable) -> None:
        """無効化リスナーを登録"""
        self.invalidation_listeners.append(callback)


class CacheInvalidationManager:
    """キャッシュ無効化マネージャー"""
    
    def __init__(
        self,
        cache: DistributedCache,
        strategy: InvalidationStrategy = InvalidationStrategy.IMMEDIATE
    ):
        """初期化"""
        self.cache = cache
        self.strategy = strategy
        self.pending_invalidations: List[tuple] = []
    
    async def invalidate_on_event(self, event_type: str, event_data: Dict) -> None:
        """イベントベースの無効化"""
        
        if self.strategy == InvalidationStrategy.IMMEDIATE:
            await self._invalidate_immediately(event_type, event_data)
        elif self.strategy == InvalidationStrategy.LAZY:
            self._schedule_lazy_invalidation(event_type, event_data)
        elif self.strategy == InvalidationStrategy.EVENT_BASED:
            await self._handle_event_invalidation(event_type, event_data)
    
    async def _invalidate_immediately(self, event_type: str, event_data: Dict) -> None:
        """即座に無効化"""
        
        # イベントタイプに基づいてキャッシュキーを生成
        keys_to_invalidate = self._get_related_keys(event_type, event_data)
        
        for key in keys_to_invalidate:
            await self.cache.delete(key)
        
        logger.info(f"Invalidated {len(keys_to_invalidate)} cache keys for event: {event_type}")
    
    def _schedule_lazy_invalidation(self, event_type: str, event_data: Dict) -> None:
        """遅延無効化をスケジュール"""
        
        self.pending_invalidations.append((event_type, event_data))
        logger.debug(f"Scheduled lazy invalidation for event: {event_type}")
    
    async def _handle_event_invalidation(self, event_type: str, event_data: Dict) -> None:
        """イベントベース無効化"""
        
        # イベントの依存関係を追跡
        # 関連する他のイベントも無効化の対象とする
        await self._invalidate_immediately(event_type, event_data)
    
    def _get_related_keys(self, event_type: str, event_data: Dict) -> List[str]:
        """関連するキャッシュキーを取得"""
        
        keys = []
        
        # イベントタイプに応じてキーを生成
        if event_type == "user_updated":
            user_id = event_data.get("user_id")
            keys = [
                f"user:{user_id}",
                f"user:{user_id}:profile",
                f"user:{user_id}:permissions"
            ]
        elif event_type == "product_updated":
            product_id = event_data.get("product_id")
            keys = [
                f"product:{product_id}",
                f"product:{product_id}:details",
                "products:list"
            ]
        elif event_type == "inventory_changed":
            product_id = event_data.get("product_id")
            keys = [
                f"product:{product_id}:inventory",
                "products:available"
            ]
        
        return keys


class CacheDecorator:
    """キャッシュデコレータ"""
    
    def __init__(self, cache: DistributedCache, ttl_seconds: Optional[int] = None):
        """初期化"""
        self.cache = cache
        self.ttl_seconds = ttl_seconds
    
    def cached(self, func: Callable) -> Callable:
        """関数の結果をキャッシュするデコレータ"""
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # キャッシュキー生成
            cache_key = f"{func.__module__}:{func.__name__}:{args}:{kwargs}"
            
            # キャッシュから取得
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # キャッシュに無い場合は実行
            result = await func(*args, **kwargs)
            
            # キャッシュに設定
            await self.cache.set(cache_key, result, self.ttl_seconds)
            
            return result
        
        return wrapper


class CacheManager:
    """キャッシュ統合管理"""
    
    def __init__(self, policy: CachePolicy = None):
        """初期化"""
        self.policy = policy or CachePolicy()
        
        # バックエンド初期化
        self.backend = InMemoryCache(self.policy)
        
        # 分散キャッシュ
        self.cache = DistributedCache(self.backend)
        
        # 無効化マネージャー
        self.invalidation_manager = CacheInvalidationManager(
            self.cache,
            InvalidationStrategy.IMMEDIATE
        )
        
        # デコレータ
        self.decorator = CacheDecorator(self.cache)
    
    async def get_stats(self) -> CacheStats:
        """統計を取得"""
        return self.backend.stats
    
    async def get_report(self) -> Dict[str, Any]:
        """レポートを取得"""
        
        stats = await self.get_stats()
        
        return {
            "policy": {
                "strategy": self.policy.strategy.value,
                "max_size_mb": self.policy.max_size_mb,
                "ttl_seconds": self.policy.ttl_seconds
            },
            "stats": {
                "hits": stats.total_hits,
                "misses": stats.total_misses,
                "hit_rate_percent": f"{stats.hit_rate:.2f}",
                "evictions": stats.total_evictions,
                "invalidations": stats.total_invalidations,
                "current_size_mb": f"{stats.current_size_mb:.2f}",
                "entry_count": stats.entry_count
            }
        }
