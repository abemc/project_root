"""
Optimization Layer for Phase 5 Learning Systems

Provides memory-efficient caching, batch processing, and parallelization
for the Phase 5 learning systems.

Key Features:
- LRU caching for frequently accessed memories
- Batch processing for multiple executions
- Async processing for non-blocking operations
- Index optimization for fast retrieval
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import logging
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheStatistics:
    """Statistics for cache performance."""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 1000
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0-1)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def __str__(self) -> str:
        return (
            f"Cache(size={self.size}/{self.max_size}, "
            f"hits={self.hits}, misses={self.misses}, "
            f"hit_rate={self.hit_rate:.1%})"
        )


class LRUMemoryCache:
    """
    Least Recently Used (LRU) cache for memory objects.
    
    Optimizes retrieval of frequently accessed memories with O(1) lookup.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.stats = CacheStatistics(max_size=max_size)
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached item or None
        """
        with self._lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.stats.hits += 1
            return self.cache[key]
    
    def put(self, key: str, value: Any):
        """
        Put item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            
            # Evict least recently used if over capacity
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
            
            self.stats.size = len(self.cache)
    
    def clear(self):
        """Clear the cache."""
        with self._lock:
            self.cache.clear()
            self.stats.size = 0
    
    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        return self.stats


class BatchProcessor:
    """
    Process multiple items in batches for efficiency.
    """
    
    def __init__(self, batch_size: int = 100, timeout_seconds: int = 5):
        """
        Initialize batch processor.
        
        Args:
            batch_size: Maximum items per batch
            timeout_seconds: Maximum time to wait before processing
        """
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.batch: List[Any] = []
        self.last_process_time = datetime.now()
        self._lock = threading.RLock()
    
    def add(self, item: Any) -> bool:
        """
        Add item to batch.
        
        Args:
            item: Item to add
            
        Returns:
            True if batch was processed
        """
        with self._lock:
            self.batch.append(item)
            return len(self.batch) >= self.batch_size
    
    def should_process(self) -> bool:
        """Check if batch should be processed."""
        with self._lock:
            if not self.batch:
                return False
            
            # Process if full or timeout exceeded
            elapsed = (datetime.now() - self.last_process_time).total_seconds()
            return len(self.batch) >= self.batch_size or elapsed >= self.timeout_seconds
    
    def get_batch(self) -> List[Any]:
        """Get current batch and reset."""
        with self._lock:
            batch = self.batch.copy()
            self.batch.clear()
            self.last_process_time = datetime.now()
            return batch


class IndexOptimizer:
    """
    Optimize memory indexing for fast retrieval.
    """
    
    def __init__(self):
        """Initialize index optimizer."""
        self.by_task_family: Dict[str, List[str]] = {}
        self.by_success: Dict[bool, List[str]] = {True: [], False: []}
        self.by_quality: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
    
    def add_memory(self, memory_id: str, task_family: str, success: bool, quality: float):
        """Add memory to indexes."""
        with self._lock:
            # Index by task family
            if task_family not in self.by_task_family:
                self.by_task_family[task_family] = []
            self.by_task_family[task_family].append(memory_id)
            
            # Index by success
            self.by_success[success].append(memory_id)
            
            # Index by quality range
            quality_range = f"{int(quality * 10) * 0.1:.1f}-{int(quality * 10) * 0.1 + 0.1:.1f}"
            if quality_range not in self.by_quality:
                self.by_quality[quality_range] = []
            self.by_quality[quality_range].append(memory_id)
    
    def find_by_family(self, task_family: str) -> List[str]:
        """Find memories by task family."""
        with self._lock:
            return self.by_task_family.get(task_family, [])
    
    def find_successful(self) -> List[str]:
        """Find all successful executions."""
        with self._lock:
            return self.by_success[True].copy()
    
    def find_by_quality_range(self, min_quality: float, max_quality: float) -> List[str]:
        """Find memories by quality range."""
        with self._lock:
            results = []
            for quality_range, memory_ids in self.by_quality.items():
                parts = quality_range.split("-")
                if len(parts) == 2:
                    try:
                        range_min = float(parts[0])
                        range_max = float(parts[1])
                        if range_min >= min_quality and range_max <= max_quality:
                            results.extend(memory_ids)
                    except ValueError:
                        pass
            return results


class PerformanceMonitor:
    """Monitor and report performance metrics."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.operation_times: Dict[str, List[float]] = {}
        self.memory_snapshots: List[Tuple[datetime, float]] = []
        self._lock = threading.RLock()
    
    def record_operation(self, operation_name: str, duration_ms: float):
        """Record operation duration."""
        with self._lock:
            if operation_name not in self.operation_times:
                self.operation_times[operation_name] = []
            self.operation_times[operation_name].append(duration_ms)
    
    def record_memory_usage(self, memory_mb: float):
        """Record memory usage snapshot."""
        with self._lock:
            self.memory_snapshots.append((datetime.now(), memory_mb))
            if len(self.memory_snapshots) > 100:
                self.memory_snapshots = self.memory_snapshots[-100:]
    
    def get_avg_duration(self, operation_name: str) -> Optional[float]:
        """Get average duration for operation."""
        with self._lock:
            times = self.operation_times.get(operation_name, [])
            return sum(times) / len(times) if times else None
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        with self._lock:
            report = {
                "operations": {},
                "memory": {
                    "samples": len(self.memory_snapshots),
                    "avg_mb": 0.0,
                    "peak_mb": 0.0,
                }
            }
            
            for op_name, times in self.operation_times.items():
                if times:
                    report["operations"][op_name] = {
                        "count": len(times),
                        "avg_ms": sum(times) / len(times),
                        "min_ms": min(times),
                        "max_ms": max(times),
                    }
            
            if self.memory_snapshots:
                memory_values = [mem for _, mem in self.memory_snapshots]
                report["memory"]["avg_mb"] = sum(memory_values) / len(memory_values)
                report["memory"]["peak_mb"] = max(memory_values)
            
            return report


# Global performance monitor
_perf_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _perf_monitor
