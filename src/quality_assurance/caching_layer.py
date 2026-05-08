"""
キャッシング層

分析結果、推論結果、ネットワーク統計のキャッシング管理を実現するシステム
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import json


class CacheLevel(Enum):
    """キャッシュレベル"""
    L1_MEMORY = "l1_memory"  # インメモリ（最速）
    L2_PERSISTENT = "l2_persistent"  # ファイル（永続）
    L3_DISTRIBUTED = "l3_distributed"  # 分散キャッシュ


class CacheInvalidationStrategy(Enum):
    """キャッシュ無効化戦略"""
    TTL = "ttl"  # 時間ベース
    LRU = "lru"  # 最後使用時間ベース
    LFU = "lfu"  # 使用頻度ベース
    EVENT = "event"  # イベントベース


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    key: str
    value: Any
    
    created_at: datetime = None
    last_accessed: datetime = None
    access_count: int = 0
    
    ttl_seconds: Optional[int] = None
    cache_level: CacheLevel = CacheLevel.L1_MEMORY
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.last_accessed is None:
            self.last_accessed = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """有効期限切れかチェック"""
        if self.ttl_seconds is None:
            return False
        
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds
    
    def touch(self) -> None:
        """アクセス情報を更新"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStatistics:
    """キャッシュ統計"""
    total_entries: int = 0
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    
    total_size_bytes: int = 0
    average_entry_size_bytes: int = 0
    
    def hit_rate(self) -> float:
        """ヒット率"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0


@dataclass
class CachePolicy:
    """キャッシュポリシー"""
    max_entries: int = 1000
    max_size_mb: float = 512.0
    default_ttl_seconds: int = 3600
    
    invalidation_strategy: CacheInvalidationStrategy = CacheInvalidationStrategy.TTL
    eviction_policy: str = "lru"  # LRU, LFU
    
    enable_compression: bool = False
    compression_threshold_bytes: int = 1024


class CachingLayer:
    """キャッシング層"""
    
    def __init__(
        self,
        policy: Optional[CachePolicy] = None
    ):
        """初期化"""
        self.policy = policy or CachePolicy()
        
        self.l1_cache: Dict[str, CacheEntry] = {}
        self.l2_cache: Dict[str, str] = {}  # ファイルパス
        
        self.statistics = CacheStatistics()
        self.access_history: List[Tuple[str, datetime]] = []
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得"""
        
        # L1メモリキャッシュをチェック
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            
            if entry.is_expired():
                del self.l1_cache[key]
                self.statistics.eviction_count += 1
            else:
                entry.touch()
                self.statistics.hit_count += 1
                return entry.value
        
        # L2永続キャッシュをチェック
        if key in self.l2_cache:
            self.statistics.hit_count += 1
            # L1に昇格
            entry = CacheEntry(
                key=key,
                value=self.l2_cache[key],
                ttl_seconds=self.policy.default_ttl_seconds,
                cache_level=CacheLevel.L2_PERSISTENT
            )
            entry.touch()
            self.l1_cache[key] = entry
            return entry.value
        
        self.statistics.miss_count += 1
        return None
    
    def put(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        cache_level: CacheLevel = CacheLevel.L1_MEMORY
    ) -> bool:
        """キャッシュに値を設定"""
        
        # サイズをチェック
        if not self._check_capacity(key, value):
            # 無効化戦略に従ってエントリを削除
            self._evict_entries()
        
        ttl = ttl_seconds or self.policy.default_ttl_seconds
        
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl,
            cache_level=cache_level
        )
        
        if cache_level == CacheLevel.L1_MEMORY:
            self.l1_cache[key] = entry
        elif cache_level == CacheLevel.L2_PERSISTENT:
            self.l2_cache[key] = str(value)
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl,
                cache_level=CacheLevel.L2_PERSISTENT
            )
            self.l1_cache[key] = entry
        
        self._update_statistics()
        self.access_history.append((key, datetime.utcnow()))
        
        return True
    
    def delete(self, key: str) -> bool:
        """キャッシュから値を削除"""
        
        deleted = False
        
        if key in self.l1_cache:
            del self.l1_cache[key]
            deleted = True
        
        if key in self.l2_cache:
            del self.l2_cache[key]
            deleted = True
        
        if deleted:
            self._update_statistics()
        
        return deleted
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.statistics = CacheStatistics()
    
    def invalidate_by_ttl(self) -> int:
        """TTLに基づいてエントリを無効化"""
        
        expired_keys = []
        
        for key, entry in self.l1_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.l1_cache[key]
            self.statistics.eviction_count += 1
        
        return len(expired_keys)
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """パターンに基づいてエントリを無効化"""
        
        matching_keys = []
        
        for key in self.l1_cache.keys():
            if pattern in key:
                matching_keys.append(key)
        
        for key in matching_keys:
            del self.l1_cache[key]
            self.statistics.eviction_count += 1
        
        return len(matching_keys)
    
    def cache_analysis_result(
        self,
        analysis_id: str,
        result: Dict[str, Any],
        ttl_seconds: int = 3600
    ) -> bool:
        """分析結果をキャッシュ"""
        
        key = f"analysis:{analysis_id}"
        return self.put(key, result, ttl_seconds, CacheLevel.L1_MEMORY)
    
    def get_analysis_result(self, analysis_id: str) -> Optional[Dict]:
        """分析結果を取得"""
        
        key = f"analysis:{analysis_id}"
        return self.get(key)
    
    def cache_assignment(
        self,
        assignment_id: str,
        assignment: Dict[str, Any],
        ttl_seconds: int = 7200
    ) -> bool:
        """割当情報をキャッシュ"""
        
        key = f"assignment:{assignment_id}"
        return self.put(key, assignment, ttl_seconds, CacheLevel.L1_MEMORY)
    
    def get_assignment(self, assignment_id: str) -> Optional[Dict]:
        """割当情報を取得"""
        
        key = f"assignment:{assignment_id}"
        return self.get(key)
    
    def cache_statistics(
        self,
        stats_type: str,
        stats_data: Dict[str, Any],
        ttl_seconds: int = 1800
    ) -> bool:
        """統計情報をキャッシュ"""
        
        key = f"stats:{stats_type}:{self._get_hour_key()}"
        return self.put(key, stats_data, ttl_seconds, CacheLevel.L2_PERSISTENT)
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """統計サマリーを取得"""
        
        return {
            "total_entries": self.statistics.total_entries,
            "hit_count": self.statistics.hit_count,
            "miss_count": self.statistics.miss_count,
            "eviction_count": self.statistics.eviction_count,
            "hit_rate": self.statistics.hit_rate(),
            "total_size_bytes": self.statistics.total_size_bytes,
            "l1_entries": len(self.l1_cache),
            "l2_entries": len(self.l2_cache)
        }
    
    def _check_capacity(self, key: str, value: Any) -> bool:
        """容量をチェック"""
        
        # エントリ数チェック
        if len(self.l1_cache) >= self.policy.max_entries:
            return False
        
        # サイズチェック（概算）
        size_bytes = self._estimate_size(value)
        current_size = sum(self._estimate_size(e.value) for e in self.l1_cache.values())
        
        max_bytes = self.policy.max_size_mb * 1024 * 1024
        return (current_size + size_bytes) <= max_bytes
    
    def _evict_entries(self) -> None:
        """エントリを削除"""
        
        if not self.l1_cache:
            return
        
        strategy = self.policy.eviction_policy
        
        if strategy == "lru":
            # 最後使用時間で削除
            entry_to_delete = min(
                self.l1_cache.values(),
                key=lambda e: e.last_accessed
            )
        elif strategy == "lfu":
            # 使用頻度で削除
            entry_to_delete = min(
                self.l1_cache.values(),
                key=lambda e: e.access_count
            )
        else:
            # デフォルトはLRU
            entry_to_delete = min(
                self.l1_cache.values(),
                key=lambda e: e.last_accessed
            )
        
        del self.l1_cache[entry_to_delete.key]
        self.statistics.eviction_count += 1
    
    def _estimate_size(self, value: Any) -> int:
        """値のサイズを推定"""
        
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (dict, list)):
                return len(json.dumps(value).encode('utf-8'))
            else:
                return len(str(value).encode('utf-8'))
        except:
            return 0
    
    def _update_statistics(self) -> None:
        """統計を更新"""
        
        self.statistics.total_entries = len(self.l1_cache) + len(self.l2_cache)
        self.statistics.total_size_bytes = sum(
            self._estimate_size(e.value) for e in self.l1_cache.values()
        )
        
        if self.statistics.total_entries > 0:
            self.statistics.average_entry_size_bytes = (
                self.statistics.total_size_bytes // self.statistics.total_entries
            )
    
    def _get_hour_key(self) -> str:
        """現在の時間キーを取得"""
        
        now = datetime.utcnow()
        return now.strftime("%Y%m%d%H")
    
    def generate_cache_report(self) -> str:
        """キャッシュレポートを生成"""
        
        stats = self.get_statistics_summary()
        
        report = []
        report.append("=" * 60)
        report.append("CACHE LAYER REPORT")
        report.append(f"Generated: {datetime.utcnow().isoformat()}")
        report.append("=" * 60)
        report.append("")
        
        # キャッシュ統計
        report.append("CACHE STATISTICS")
        report.append("-" * 60)
        report.append(f"Total Entries: {stats['total_entries']}")
        report.append(f"L1 (Memory): {stats['l1_entries']}")
        report.append(f"L2 (Persistent): {stats['l2_entries']}")
        report.append(f"Total Size: {stats['total_size_bytes'] / 1024:.2f} KB")
        report.append(f"Hit Count: {stats['hit_count']}")
        report.append(f"Miss Count: {stats['miss_count']}")
        report.append(f"Hit Rate: {stats['hit_rate']:.1%}")
        report.append(f"Evictions: {stats['eviction_count']}")
        report.append("")
        
        # ポリシー
        report.append("CACHE POLICY")
        report.append("-" * 60)
        report.append(f"Max Entries: {self.policy.max_entries}")
        report.append(f"Max Size: {self.policy.max_size_mb} MB")
        report.append(f"Default TTL: {self.policy.default_ttl_seconds}s")
        report.append(f"Eviction: {self.policy.eviction_policy}")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
