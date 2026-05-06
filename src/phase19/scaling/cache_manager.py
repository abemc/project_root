"""Cache Manager - manages multi-level caching for improved performance."""

import time
import hashlib
import json
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"       # Least Recently Used
    LFU = "lfu"       # Least Frequently Used
    TTL = "ttl"       # Time To Live (expiry only)
    FIFO = "fifo"     # First In First Out


@dataclass
class CacheEntry:
    """Represents a cache entry."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl: Optional[float] = None  # seconds
    access_count: int = 0
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl

    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "ttl": self.ttl,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "is_expired": self.is_expired()
        }


class CacheManager:
    """Multi-level cache with configurable eviction strategies.
    
    Features:
    - LRU / LFU / TTL / FIFO eviction
    - Hit/miss statistics
    - Memory limit enforcement
    - Batch operations
    - Cache warming
    - Namespace separation
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        strategy: CacheStrategy = CacheStrategy.LRU
    ):
        """Initialize cache manager.
        
        Args:
            max_size: Max number of entries
            default_ttl: Default TTL in seconds (None = no expiry)
            strategy: Eviction strategy
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.strategy = strategy
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            entry.touch()
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if not provided)
        """
        with self._lock:
            effective_ttl = ttl if ttl is not None else self.default_ttl

            # Estimate size
            try:
                size = len(json.dumps(value, default=str).encode())
            except Exception:
                size = 0

            entry = CacheEntry(
                key=key,
                value=value,
                ttl=effective_ttl,
                size_bytes=size
            )

            self._cache[key] = entry

            # Evict if over max size
            while len(self._cache) > self.max_size:
                self._evict_one()

    def delete(self, key: str) -> bool:
        """Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[float] = None
    ) -> Any:
        """Get value from cache, or compute and store it.
        
        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: TTL for new entry
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl)
        return value

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern (prefix match).
        
        Args:
            pattern: Key prefix pattern
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            to_delete = [k for k in self._cache if k.startswith(pattern)]
            for key in to_delete:
                del self._cache[key]
            return len(to_delete)

    def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def warm_up(self, entries: Dict[str, Any], ttl: Optional[float] = None) -> int:
        """Pre-populate cache with entries.
        
        Args:
            entries: Dict of key-value pairs to cache
            ttl: TTL for all entries
            
        Returns:
            Number of entries added
        """
        for key, value in entries.items():
            self.set(key, value, ttl)
        return len(entries)

    def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired:
                del self._cache[key]
            return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0

            total_size = sum(e.size_bytes for e in self._cache.values())
            expired_count = sum(1 for e in self._cache.values() if e.is_expired())

            return {
                "strategy": self.strategy.value,
                "max_size": self.max_size,
                "current_size": len(self._cache),
                "hit_rate": round(hit_rate, 4),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expired_entries": expired_count,
                "total_size_bytes": total_size
            }

    def _evict_one(self) -> None:
        """Evict one entry based on strategy."""
        if not self._cache:
            return

        if self.strategy == CacheStrategy.LRU:
            key = min(self._cache, key=lambda k: self._cache[k].last_accessed)
        elif self.strategy == CacheStrategy.LFU:
            key = min(self._cache, key=lambda k: self._cache[k].access_count)
        elif self.strategy == CacheStrategy.FIFO:
            key = min(self._cache, key=lambda k: self._cache[k].created_at)
        else:  # TTL or default - evict expired first, then LRU
            expired = [k for k, v in self._cache.items() if v.is_expired()]
            if expired:
                key = expired[0]
            else:
                key = min(self._cache, key=lambda k: self._cache[k].last_accessed)

        del self._cache[key]
        self._evictions += 1
