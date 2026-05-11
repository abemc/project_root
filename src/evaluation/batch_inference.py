"""
バッチ処理推論パイプライン
効率的な大規模推論を実現
"""

from typing import List, Dict, Any, Optional, Callable
import logging
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BatchInferenceConfig:
    """バッチ推論の設定"""
    batch_size: int = 32
    max_queue_size: int = 1000
    timeout_per_batch: float = 300.0  # 5分
    prefetch_batches: int = 2
    enable_caching: bool = True
    cache_size: int = 10000


class BatchInferencePipeline:
    """
    バッチ処理推論パイプライン
    
    機能:
    - 効率的なバッチ処理
    - キャッシング機構
    - エラーハンドリング
    - パフォーマンス最適化
    """
    
    def __init__(self, config: Optional[BatchInferenceConfig] = None):
        """
        初期化
        
        Args:
            config: バッチ推論設定
        """
        self.config = config or BatchInferenceConfig()
        self.cache: Dict[str, str] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.processed_count = 0
    
    def process_batch(
        self,
        items: List[Dict[str, Any]],
        inference_fn: Callable[[Dict[str, Any]], str],
        use_cache: bool = True,
    ) -> List[str]:
        """
        バッチを処理
        
        Args:
            items: 処理対象のアイテムリスト
            inference_fn: 推論関数
            use_cache: キャッシュを使用するか
            
        Returns:
            List[str]: 推論結果
        """
        results = []
        
        for item in items:
            # キャッシュキーの生成
            if use_cache and self.config.enable_caching:
                cache_key = self._generate_cache_key(item)
                
                # キャッシュからの取得
                if cache_key in self.cache:
                    results.append(self.cache[cache_key])
                    self.cache_hits += 1
                    continue
            
            # キャッシュミス：推論実行
            try:
                result = inference_fn(item)
                results.append(result)
                
                # キャッシュに保存
                if use_cache and self.config.enable_caching:
                    self._add_to_cache(cache_key, result)
                
                self.cache_misses += 1
            except Exception as e:
                logger.warning(f"Inference error: {e}")
                results.append('ERROR')
        
        self.processed_count += len(items)
        return results
    
    def process_batches_sequential(
        self,
        dataset: List[Dict[str, Any]],
        inference_fn: Callable[[Dict[str, Any]], str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[str]:
        """
        データセットをバッチ単位で順序に処理
        
        Args:
            dataset: 処理対象のデータセット
            inference_fn: 推論関数
            progress_callback: 進捗コールバック関数 (current, total)
            
        Returns:
            List[str]: すべての推論結果
        """
        all_results = []
        batch_size = self.config.batch_size
        total_items = len(dataset)
        total_batches = (total_items + batch_size - 1) // batch_size
        
        logger.info(f"Processing {total_items} items in {total_batches} batches (size={batch_size})")
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_items)
            batch = dataset[start_idx:end_idx]
            
            # バッチ処理
            batch_results = self.process_batch(batch, inference_fn)
            all_results.extend(batch_results)
            
            # 進捗報告
            if progress_callback:
                progress_callback(batch_idx + 1, total_batches)
            
            logger.debug(f"Batch {batch_idx+1}/{total_batches} completed")
        
        return all_results
    
    def _generate_cache_key(self, item: Dict[str, Any]) -> str:
        """
        アイテムからキャッシュキーを生成
        
        Args:
            item: アイテム
            
        Returns:
            str: キャッシュキー
        """
        # 主要なフィールドからキーを生成
        key_parts = []
        for field in ['question', 'problem', 'prompt', 'text']:
            if field in item:
                key_parts.append(str(item[field])[:50])  # 最初の50文字
        
        return '|'.join(key_parts) if key_parts else str(hash(str(item)))
    
    def _add_to_cache(self, key: str, value: str):
        """
        キャッシュに追加
        
        Args:
            key: キャッシュキー
            value: キャッシュ値
        """
        if len(self.cache) >= self.config.cache_size:
            # キャッシュが満杯の場合は古いエントリを削除
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = value
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        キャッシュ統計を取得
        
        Returns:
            Dict: 統計情報
        """
        total_accesses = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_accesses * 100) if total_accesses > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_accesses': total_accesses,
            'hit_rate': hit_rate,
            'cache_size': len(self.cache),
            'processed_items': self.processed_count,
        }
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self.cache.clear()
        logger.info("Cache cleared")


class DynamicBatchSizeOptimizer:
    """
    動的バッチサイズ最適化
    
    メモリ使用量と推論速度のバランスを取る
    """
    
    def __init__(
        self,
        initial_batch_size: int = 32,
        max_memory_mb: int = 2048,
    ):
        """
        初期化
        
        Args:
            initial_batch_size: 初期バッチサイズ
            max_memory_mb: 最大メモリ (MB)
        """
        self.batch_size = initial_batch_size
        self.max_memory_mb = max_memory_mb
        self.batch_timings: List[float] = []
        self.batch_sizes_tried: List[int] = []
    
    def suggest_batch_size(self) -> int:
        """
        推奨バッチサイズを提案
        
        Returns:
            int: 推奨バッチサイズ
        """
        if not self.batch_timings or not self.batch_sizes_tried:
            return self.batch_size
        
        # スループット最大のバッチサイズを選択
        throughputs = [
            size / time if time > 0 else 0
            for size, time in zip(self.batch_sizes_tried, self.batch_timings)
        ]
        
        if throughputs:
            best_idx = np.argmax(throughputs)
            return self.batch_sizes_tried[best_idx]
        
        return self.batch_size
    
    def record_batch_performance(
        self,
        batch_size: int,
        inference_time: float,
    ):
        """
        バッチのパフォーマンスを記録
        
        Args:
            batch_size: バッチサイズ
            inference_time: 推論時間 (秒)
        """
        self.batch_sizes_tried.append(batch_size)
        self.batch_timings.append(inference_time)
    
    def adjust_batch_size(self, memory_usage_mb: float) -> int:
        """
        メモリ使用量に基づいてバッチサイズを調整
        
        Args:
            memory_usage_mb: メモリ使用量 (MB)
            
        Returns:
            int: 調整後のバッチサイズ
        """
        if memory_usage_mb > self.max_memory_mb * 0.9:
            # メモリ使用量が多い場合は減少
            self.batch_size = max(1, int(self.batch_size * 0.8))
            logger.info(f"Reduced batch size to {self.batch_size} (memory: {memory_usage_mb:.1f}MB)")
        elif memory_usage_mb < self.max_memory_mb * 0.5:
            # メモリに余裕がある場合は増加
            self.batch_size = int(self.batch_size * 1.2)
            logger.info(f"Increased batch size to {self.batch_size} (memory: {memory_usage_mb:.1f}MB)")
        
        return self.batch_size


class ParallelBatchProcessor:
    """
    並列バッチプロセッサ
    複数ワーカーでバッチを並列処理
    """
    
    def __init__(self, num_workers: int = 4):
        """
        初期化
        
        Args:
            num_workers: ワーカー数
        """
        self.num_workers = num_workers
        self.worker_stats = {i: {'processed': 0, 'errors': 0} for i in range(num_workers)}
    
    def process_batch_parallel(
        self,
        batch: List[Dict[str, Any]],
        inference_fn: Callable[[Dict[str, Any]], str],
    ) -> List[str]:
        """
        バッチを並列処理（シミュレーション）
        
        Args:
            batch: 処理対象のバッチ
            inference_fn: 推論関数
            
        Returns:
            List[str]: 推論結果
        """
        # 注: 実際の並列処理はマルチプロセッシングやマルチスレッドで実装
        # ここでは順序処理のシミュレーション
        results = []
        len(batch) // self.num_workers
        
        worker_id = 0
        for idx, item in enumerate(batch):
            worker_id = idx % self.num_workers
            
            try:
                result = inference_fn(item)
                results.append(result)
                self.worker_stats[worker_id]['processed'] += 1
            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                results.append('ERROR')
                self.worker_stats[worker_id]['errors'] += 1
        
        return results
    
    def get_worker_statistics(self) -> Dict[int, Dict[str, int]]:
        """ワーカーの統計を取得"""
        return self.worker_stats.copy()
