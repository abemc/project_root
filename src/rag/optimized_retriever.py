"""
Phase 7 RAG 最適化リトリーバー
- キャッシング戦略
- 非同期・並列処理
- データベースクエリ最適化
- メモリ効率化
"""

import asyncio
import hashlib
import logging
from functools import lru_cache
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time

from src.rag.knowledge_integration_engine import Phase7KnowledgeIntegrationEngine
from src.self_improvement.domain_knowledge import DomainKnowledgeManager


logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """キャッシュ統計"""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def hit_rate(self) -> float:
        """キャッシュヒット率"""
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries
    
    def get_summary(self) -> str:
        """統計サマリー"""
        return f"キャッシュ統計: 総クエリ={self.total_queries}, ヒット={self.cache_hits}, ミス={self.cache_misses}, ヒット率={self.hit_rate:.1%}"


class OptimizedMultiDomainRetriever:
    """最適化版マルチドメインリトリーバー"""
    
    def __init__(self, 
                 embedding_model=None,
                 corpus_index=None,
                 cache_size: int = 256,
                 enable_async: bool = True,
                 max_workers: int = 4):
        """
        Args:
            embedding_model: 埋め込みモデル
            corpus_index: コーパスインデックス
            cache_size: キャッシュサイズ（最大件数）
            enable_async: 非同期処理有効化フラグ
            max_workers: スレッドプール最大ワーカー数
        """
        self.embedding_model = embedding_model
        self.corpus_index = corpus_index
        self.cache_size = cache_size
        self.enable_async = enable_async
        
        # コンポーネント初期化
        self.integration_engine = Phase7KnowledgeIntegrationEngine()
        self.domain_manager = DomainKnowledgeManager()
        
        # キャッシュ初期化
        self._query_cache = {}
        self._domain_cache = {}
        self._domain_keyword_cache = {}
        self.cache_stats = CacheStats()
        
        # 並列処理用
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    # ==================== キャッシング機構 ====================
    
    def _get_cache_key(self, query: str, primary_domain: str, 
                      related_domains: Optional[List[str]] = None,
                      top_k: int = 5) -> str:
        """キャッシュキーの生成"""
        domains_str = ",".join(sorted(related_domains or []))
        key_str = f"{query}_{primary_domain}_{domains_str}_{top_k}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[Dict]:
        """キャッシュ確認"""
        self.cache_stats.total_queries += 1
        
        if cache_key in self._query_cache:
            self.cache_stats.cache_hits += 1
            logger.debug(f"キャッシュヒット: {cache_key[:8]}...")
            return self._query_cache[cache_key]
        
        self.cache_stats.cache_misses += 1
        return None
    
    def _store_cache(self, cache_key: str, results: Dict) -> None:
        """キャッシュ保存（LRU戦略）"""
        if len(self._query_cache) >= self.cache_size:
            # 最も古いキーを削除
            oldest_key = next(iter(self._query_cache))
            del self._query_cache[oldest_key]
            logger.debug(f"キャッシュオーバーフロー: {oldest_key[:8]}...を削除")
        
        self._query_cache[cache_key] = results
        logger.debug(f"キャッシュ保存: {cache_key[:8]}...（{len(self._query_cache)}/{self.cache_size}）")
    
    @lru_cache(maxsize=128)
    def _get_domain_keywords_cached(self, domain: str) -> Tuple[str, ...]:
        """ドメインキーワードのLRUキャッシング"""
        logger.debug(f"ドメインキーワード取得: {domain}")
        keywords = self.domain_manager.get_domain_keywords(domain)
        return tuple(keywords) if isinstance(keywords, list) else (keywords,)
    
    def clear_cache(self) -> None:
        """キャッシュクリア"""
        self._query_cache.clear()
        self._domain_cache.clear()
        self._domain_keyword_cache.clear()
        self._get_domain_keywords_cached.cache_clear()
        logger.info("キャッシュをクリアしました")
    
    def get_cache_stats(self) -> CacheStats:
        """キャッシュ統計取得"""
        return self.cache_stats
    
    # ==================== 最適化検索 ====================
    
    def retrieve_multi_domain_optimized(
        self,
        query: str,
        primary_domain: str,
        related_domains: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict:
        """
        最適化版マルチドメイン検索
        キャッシングと並列処理を活用
        """
        related_domains = related_domains or []
        start_time = time.time()
        
        # キャッシュ確認
        cache_key = self._get_cache_key(query, primary_domain, related_domains, top_k)
        cached_result = self._check_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        # 非同期処理または同期処理で実行
        if self.enable_async:
            try:
                result = asyncio.run(
                    self._retrieve_multi_domain_async(
                        query, primary_domain, related_domains, top_k
                    )
                )
            except RuntimeError:
                # イベントループが既に実行中の場合は同期処理
                result = self._retrieve_multi_domain_sync(
                    query, primary_domain, related_domains, top_k
                )
        else:
            result = self._retrieve_multi_domain_sync(
                query, primary_domain, related_domains, top_k
            )
        
        # メタデータ追加
        elapsed = time.time() - start_time
        result['metadata'] = {
            'elapsed_ms': elapsed * 1000,
            'cache_hit': False,
            'async_mode': self.enable_async
        }
        
        # キャッシュ保存
        self._store_cache(cache_key, result)
        
        logger.info(f"検索完了: {elapsed:.3f}秒 (キャッシュ: {result['metadata']['cache_hit']})")
        
        return result
    
    def _retrieve_multi_domain_sync(
        self,
        query: str,
        primary_domain: str,
        related_domains: List[str],
        top_k: int
    ) -> Dict:
        """同期型マルチドメイン検索"""
        logger.debug(f"同期検索開始: query='{query}', primary={primary_domain}")
        
        # 主要ドメイン検索
        primary_results = self._search_domain(query, primary_domain, top_k)
        
        # 関連ドメイン検索
        cross_domain_results = {}
        domain_top_k = max(1, top_k // max(1, len(related_domains)))
        
        for domain in related_domains:
            cross_domain_results[domain] = self._search_domain(query, domain, domain_top_k)
        
        # 知識統合
        integrated = self._integrate_knowledge(
            query, primary_domain, related_domains,
            primary_results, cross_domain_results
        )
        
        return {
            'primary_results': primary_results,
            'cross_domain_results': cross_domain_results,
            'integrated': integrated,
            'status': 'success'
        }
    
    async def _retrieve_multi_domain_async(
        self,
        query: str,
        primary_domain: str,
        related_domains: List[str],
        top_k: int
    ) -> Dict:
        """非同期型マルチドメイン検索"""
        logger.debug(f"非同期検索開始: query='{query}', primary={primary_domain}")
        
        domain_top_k = max(1, top_k // max(1, len(related_domains)))
        
        # 全ドメインの検索タスク生成
        tasks = [
            asyncio.create_task(
                self._search_domain_async(query, primary_domain, top_k)
            )
        ]
        
        domain_tasks = {}
        for domain in related_domains:
            domain_tasks[domain] = asyncio.create_task(
                self._search_domain_async(query, domain, domain_top_k)
            )
            tasks.append(domain_tasks[domain])
        
        # 全タスク実行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 結果整理
        primary_results = results[0]
        cross_domain_results = {
            domain: domain_tasks[domain].result()
            for domain in related_domains
        }
        
        # 知識統合
        integrated = self._integrate_knowledge(
            query, primary_domain, related_domains,
            primary_results, cross_domain_results
        )
        
        return {
            'primary_results': primary_results,
            'cross_domain_results': cross_domain_results,
            'integrated': integrated,
            'status': 'success'
        }
    
    # ==================== ドメイン別検索 ====================
    
    def _search_domain(self, query: str, domain: str, top_k: int) -> List:
        """特定ドメイン検索（同期）"""
        logger.debug(f"ドメイン検索: domain={domain}, top_k={top_k}")
        
        # キーワード抽出（キャッシュ活用）
        self._get_domain_keywords_cached(domain)
        
        # 埋め込み生成（実装時に具体化）
        if self.embedding_model:
            query_embedding = self.embedding_model.encode(query)
            # コーパスから検索（実装時に具体化）
            results = self.corpus_index.search(query_embedding, top_k) \
                if self.corpus_index else []
        else:
            results = []
        
        logger.debug(f"ドメイン検索結果: {len(results)}件取得")
        return results
    
    async def _search_domain_async(self, query: str, domain: str, top_k: int) -> List:
        """特定ドメイン検索（非同期）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._search_domain,
            query, domain, top_k
        )
    
    # ==================== 知識統合 ====================
    
    def _integrate_knowledge(
        self,
        query: str,
        primary_domain: str,
        related_domains: List[str],
        primary_results: List,
        cross_domain_results: Dict
    ) -> Dict:
        """知識統合エンジンで複数ドメイン知識を統合"""
        logger.debug(f"知識統合開始: primary={primary_domain}, related={related_domains}")
        
        try:
            # 統合エンジンで処理
            integrated = self.integration_engine.integrate_and_reason(
                query=query,
                primary_domain=primary_domain,
                primary_knowledge=primary_results,
                related_domains=related_domains,
                related_knowledge={
                    domain: cross_domain_results[domain]
                    for domain in related_domains
                }
            )
            logger.debug("知識統合完了")
            return integrated
        except Exception as e:
            logger.error(f"知識統合エラー: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'primary_facts': primary_results,
                'cross_domain_facts': cross_domain_results
            }
    
    # ==================== ユーティリティ ====================
    
    def get_performance_metrics(self) -> Dict:
        """パフォーマンスメトリクス取得"""
        return {
            'cache_stats': {
                'total_queries': self.cache_stats.total_queries,
                'cache_hits': self.cache_stats.cache_hits,
                'cache_misses': self.cache_stats.cache_misses,
                'hit_rate': f"{self.cache_stats.hit_rate:.1%}",
                'cache_size': len(self._query_cache)
            },
            'cache_capacity': self.cache_size,
            'async_enabled': self.enable_async
        }
    
    def print_performance_report(self) -> None:
        """パフォーマンスレポート表示"""
        metrics = self.get_performance_metrics()
        print("\n📊 パフォーマンスメトリクス:")
        print(f"  キャッシュ統計: {self.cache_stats.get_summary()}")
        print(f"  キャッシュ使用: {metrics['cache_stats']['cache_size']}/{metrics['cache_capacity']}")
        print(f"  非同期処理: {'有効' if self.enable_async else '無効'}")
    
    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
