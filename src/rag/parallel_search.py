"""
RAG検索並列化エンジン
複数インデックス/データソースの並列検索
非同期処理、キャッシング、リランキング対応
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum
import time
import logging
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class SearchSourceType(Enum):
    """検索ソースのタイプ"""
    DENSE_VECTOR = "dense_vector"  # Embedding ベース
    SPARSE_VECTOR = "sparse_vector"  # BM25等
    HYBRID = "hybrid"  # 複合検索
    GRAPH = "graph"  # グラフデータベース
    SQL = "sql"  # SQL データベース
    EXTERNAL_API = "external_api"  # 外部API


@dataclass
class SearchResult:
    """検索結果"""
    query: str
    source: str
    source_type: SearchSourceType
    documents: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    search_time_ms: float = 0.0
    retrieval_count: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "source": self.source,
            "source_type": self.source_type.value,
            "document_count": len(self.documents),
            "avg_score": sum(self.scores) / len(self.scores) if self.scores else 0.0,
            "search_time_ms": self.search_time_ms,
            "error": self.error,
        }


@dataclass
class ParallelSearchRequest:
    """並列検索リクエスト"""
    query: str
    sources: List[str]  # 検索対象のソース名
    top_k: int = 10
    filters: Optional[Dict] = None
    timeout_seconds: float = 30.0
    enable_cache: bool = True
    rerank: bool = True


@dataclass
class MergedSearchResult:
    """マージされた検索結果"""
    query: str
    merged_documents: List[Dict[str, Any]]
    merged_scores: List[float]
    source_breakdown: Dict[str, int]  # 各ソースのドキュメント数
    search_results: List[SearchResult]
    total_search_time_ms: float
    rerank_applied: bool
    duplication_ratio: float  # 重複除外率


class SearchIndex(ABC):
    """検索インデックスの抽象基底クラス"""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> SearchResult:
        """非同期検索"""
        pass
    
    @abstractmethod
    def index_name(self) -> str:
        """インデックス名"""
        pass


class MockDenseVectorIndex(SearchIndex):
    """デモ用デンスベクトルインデックス"""
    
    def __init__(self, name: str = "dense_index"):
        self._name = name
        self.documents = {
            "doc1": {"title": "Paris", "content": "Paris is the capital of France", "embedding": [0.1, 0.2, 0.3]},
            "doc2": {"title": "Tokyo", "content": "Tokyo is the capital of Japan", "embedding": [0.15, 0.25, 0.35]},
            "doc3": {"title": "Eiffel Tower", "content": "The Eiffel Tower is in Paris", "embedding": [0.12, 0.22, 0.32]},
            "doc4": {"title": "Louvre", "content": "The Louvre is a museum in Paris", "embedding": [0.11, 0.21, 0.31]},
        }
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> SearchResult:
        """デモ検索"""
        await asyncio.sleep(0.1)  # シミュレート
        
        # キーワード マッチング
        query_lower = query.lower()
        results = []
        
        for doc_id, doc in self.documents.items():
            score = 0.0
            content_lower = (doc["title"] + " " + doc["content"]).lower()
            
            if "paris" in query_lower and "paris" in content_lower:
                score += 0.8
            if "capital" in query_lower and "capital" in content_lower:
                score += 0.6
            if "france" in query_lower and "france" in content_lower:
                score += 0.5
            if "tokyo" in query_lower and "tokyo" in content_lower:
                score += 0.8
            
            if score > 0:
                results.append((doc_id, doc, score))
        
        # スコアでソート
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:top_k]
        
        return SearchResult(
            query=query,
            source=self._name,
            source_type=SearchSourceType.DENSE_VECTOR,
            documents=[doc for _, doc, _ in results],
            scores=[score for _, _, score in results],
            search_time_ms=100.0,
            retrieval_count=len(results),
        )
    
    def index_name(self) -> str:
        return self._name


class MockSparseVectorIndex(SearchIndex):
    """デモ用スパースベクトルインデックス（BM25風）"""
    
    def __init__(self, name: str = "sparse_index"):
        self._name = name
        self.documents = {
            "doc5": {"title": "France", "content": "France is a country in Western Europe"},
            "doc6": {"title": "Japan", "content": "Japan is a country in East Asia"},
            "doc7": {"title": "London", "content": "London is the capital of England"},
        }
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> SearchResult:
        """BM25スタイルの検索"""
        await asyncio.sleep(0.05)  # シミュレート
        
        query_terms = query.lower().split()
        results = []
        
        for doc_id, doc in self.documents.items():
            content = (doc["title"] + " " + doc["content"]).lower()
            term_matches = sum(1 for term in query_terms if term in content)
            
            if term_matches > 0:
                score = term_matches / len(query_terms)
                results.append((doc_id, doc, score))
        
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:top_k]
        
        return SearchResult(
            query=query,
            source=self._name,
            source_type=SearchSourceType.SPARSE_VECTOR,
            documents=[doc for _, doc, _ in results],
            scores=[score for _, _, score in results],
            search_time_ms=50.0,
            retrieval_count=len(results),
        )
    
    def index_name(self) -> str:
        return self._name


class SearchResultCache:
    """検索結果キャッシング"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Tuple[SearchResult, float]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[SearchResult]:
        """キャッシュから取得"""
        if key not in self.cache:
            return None
        
        result, timestamp = self.cache[key]
        
        # TTLチェック
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            return None
        
        return result
    
    def put(self, key: str, result: SearchResult) -> None:
        """キャッシュに保存"""
        self.cache[key] = (result, time.time())
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        self.cache.clear()
    
    def get_stats(self) -> Dict:
        """キャッシュ統計"""
        return {
            "cache_size": len(self.cache),
            "cache_entries": list(self.cache.keys()),
        }


class SearchResultRanker:
    """検索結果のリランキング"""
    
    @staticmethod
    def remove_duplicates(
        documents: List[Dict],
        scores: List[float],
        similarity_threshold: float = 0.8,
    ) -> Tuple[List[Dict], List[float], float]:
        """重複を除去"""
        seen_contents = set()
        unique_documents = []
        unique_scores = []
        
        for doc, score in zip(documents, scores):
            content = doc.get("content", "").lower()[:100]  # 最初の100文字
            
            # 完全一致チェック
            if content not in seen_contents:
                unique_documents.append(doc)
                unique_scores.append(score)
                seen_contents.add(content)
        
        duplication_ratio = 1 - (len(unique_documents) / max(1, len(documents)))
        
        return unique_documents, unique_scores, duplication_ratio
    
    @staticmethod
    def rerank_by_sources(
        documents: List[Dict],
        scores: List[float],
        source_weights: Dict[str, float],
    ) -> Tuple[List[Dict], List[float]]:
        """ソースの重みでリランキング"""
        scored_docs = []
        
        for doc, score in zip(documents, scores):
            source = doc.get("source", "unknown")
            weight = source_weights.get(source, 1.0)
            adjusted_score = score * weight
            scored_docs.append((doc, adjusted_score))
        
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        reranked_docs = [doc for doc, _ in scored_docs]
        reranked_scores = [score for _, score in scored_docs]
        
        return reranked_docs, reranked_scores
    
    @staticmethod
    def fusion_scores(
        result1: SearchResult,
        result2: SearchResult,
        alpha: float = 0.5,
    ) -> Tuple[List[Dict], List[float]]:
        """
        複数の検索結果をマージ（スコア融合）
        RRF (Reciprocal Rank Fusion) アルゴリズム
        """
        doc_scores: Dict[str, float] = {}
        doc_data: Dict[str, Dict] = {}
        
        # 結果1からスコアを計算
        for rank, (doc, score) in enumerate(zip(result1.documents, result1.scores)):
            doc_id = doc.get("title", "")
            rrf_score = 1.0 / (rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score * alpha
            if doc_id not in doc_data:
                doc_data[doc_id] = doc
        
        # 結果2からスコアを計算
        for rank, (doc, score) in enumerate(zip(result2.documents, result2.scores)):
            doc_id = doc.get("title", "")
            rrf_score = 1.0 / (rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score * (1 - alpha)
            if doc_id not in doc_data:
                doc_data[doc_id] = doc
        
        # スコアでソート
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        merged_docs = [doc_data[doc_id] for doc_id, _ in sorted_docs]
        merged_scores = [score for _, score in sorted_docs]
        
        return merged_docs, merged_scores


class ParallelSearchEngine:
    """並列検索エンジン"""
    
    def __init__(self):
        self.indices: Dict[str, SearchIndex] = {}
        self.cache = SearchResultCache()
        self.ranker = SearchResultRanker()
        self.logger = logging.getLogger(__name__)
    
    def register_index(self, name: str, index: SearchIndex) -> None:
        """インデックスを登録"""
        self.indices[name] = index
        self.logger.info(f"Registered search index: {name}")
    
    async def search_parallel(
        self,
        request: ParallelSearchRequest,
    ) -> MergedSearchResult:
        """並列検索実行"""
        start_time = time.time()
        
        # キャッシュキーを生成
        cache_key = f"{request.query}:{','.join(request.sources)}:{request.top_k}"
        
        # キャッシュを確認
        if request.enable_cache:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.debug(f"Cache hit for: {cache_key}")
                # キャッシュから取得した場合でもMergedSearchResultを返す必要があります
                # ここでは省略
        
        # 各インデックスに対して並列検索を実行
        search_tasks = []
        for source_name in request.sources:
            if source_name in self.indices:
                index = self.indices[source_name]
                task = self._search_with_timeout(
                    index,
                    request.query,
                    request.top_k,
                    request.filters,
                    request.timeout_seconds,
                )
                search_tasks.append(task)
        
        # すべての検索を並行実行
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # エラーをフィルタリング
        valid_results = [r for r in results if isinstance(r, SearchResult) and r.error is None]
        
        # 検索結果をマージ
        merged_result = self._merge_results(request.query, valid_results, request.top_k)
        
        # リランキング
        if request.rerank:
            merged_result = await self._rerank_results(merged_result)
        
        # キャッシュに保存
        if request.enable_cache:
            self.cache.put(cache_key, merged_result.search_results[0] if merged_result.search_results else None)
        
        # 総検索時間を計算
        total_time = (time.time() - start_time) * 1000
        merged_result.total_search_time_ms = total_time
        
        return merged_result
    
    async def _search_with_timeout(
        self,
        index: SearchIndex,
        query: str,
        top_k: int,
        filters: Optional[Dict],
        timeout_seconds: float,
    ) -> SearchResult:
        """タイムアウト付き検索"""
        try:
            result = await asyncio.wait_for(
                index.search(query, top_k, filters),
                timeout=timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            return SearchResult(
                query=query,
                source=index.index_name(),
                source_type=SearchSourceType.DENSE_VECTOR,
                error=f"Search timeout after {timeout_seconds}s",
            )
        except Exception as e:
            return SearchResult(
                query=query,
                source=index.index_name(),
                source_type=SearchSourceType.DENSE_VECTOR,
                error=str(e),
            )
    
    def _merge_results(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int,
    ) -> MergedSearchResult:
        """検索結果をマージ"""
        all_documents = []
        all_scores = []
        source_breakdown = defaultdict(int)
        
        for result in results:
            for doc, score in zip(result.documents, result.scores):
                doc["_source"] = result.source
                all_documents.append(doc)
                all_scores.append(score)
                source_breakdown[result.source] += 1
        
        # 重複を除去
        unique_docs, unique_scores, dup_ratio = self.ranker.remove_duplicates(
            all_documents,
            all_scores,
        )
        
        # スコアでソート
        sorted_items = sorted(zip(unique_docs, unique_scores), key=lambda x: x[1], reverse=True)
        sorted_docs = [doc for doc, _ in sorted_items[:top_k]]
        sorted_scores = [score for _, score in sorted_items[:top_k]]
        
        return MergedSearchResult(
            query=query,
            merged_documents=sorted_docs,
            merged_scores=sorted_scores,
            source_breakdown=dict(source_breakdown),
            search_results=results,
            total_search_time_ms=0.0,
            rerank_applied=False,
            duplication_ratio=dup_ratio,
        )
    
    async def _rerank_results(self, merged_result: MergedSearchResult) -> MergedSearchResult:
        """結果をリランキング"""
        # ソース重み付けでリランキング
        source_weights = {
            source: (1.0 - i * 0.1) for i, source in enumerate(merged_result.source_breakdown.keys())
        }
        
        reranked_docs, reranked_scores = self.ranker.rerank_by_sources(
            merged_result.merged_documents,
            merged_result.merged_scores,
            source_weights,
        )
        
        merged_result.merged_documents = reranked_docs
        merged_result.merged_scores = reranked_scores
        merged_result.rerank_applied = True
        
        return merged_result
    
    def get_cache_stats(self) -> Dict:
        """キャッシュ統計を取得"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self.cache.clear()


# 使用例
async def example_parallel_search():
    """並列検索の使用例"""
    engine = ParallelSearchEngine()
    
    # インデックスを登録
    engine.register_index("dense", MockDenseVectorIndex("dense_index"))
    engine.register_index("sparse", MockSparseVectorIndex("sparse_index"))
    
    # 並列検索リクエスト
    request = ParallelSearchRequest(
        query="What is the capital of France?",
        sources=["dense", "sparse"],
        top_k=5,
        enable_cache=True,
        rerank=True,
    )
    
    # 検索実行
    result = await engine.search_parallel(request)
    
    print(f"Query: {result.query}")
    print(f"Total results: {len(result.merged_documents)}")
    print(f"Search time: {result.total_search_time_ms:.2f}ms")
    print(f"Source breakdown: {result.source_breakdown}")
    print(f"Duplication ratio: {result.duplication_ratio:.2%}")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(example_parallel_search())
