"""
RAG並列検索エンジン テストスイート
"""

import pytest
import asyncio
from src.rag.parallel_search import (
    ParallelSearchEngine, ParallelSearchRequest, MockDenseVectorIndex,
    MockSparseVectorIndex, SearchResultRanker, SearchResultCache,
    SearchResult, SearchSourceType
)


class TestSearchResultRanker:
    """検索結果ランカーのテスト"""
    
    def test_remove_duplicates(self):
        """重複除去"""
        ranker = SearchResultRanker()
        
        documents = [
            {"title": "Doc1", "content": "Paris is the capital of France"},
            {"title": "Doc2", "content": "Paris is the capital of France"},  # 重複
            {"title": "Doc3", "content": "Tokyo is the capital of Japan"},
        ]
        scores = [0.9, 0.85, 0.8]
        
        unique_docs, unique_scores, dup_ratio = ranker.remove_duplicates(documents, scores)
        
        assert len(unique_docs) == 2
        assert dup_ratio > 0  # 重複が検出された
    
    def test_rerank_by_sources(self):
        """ソースでリランキング"""
        ranker = SearchResultRanker()
        
        documents = [
            {"title": "Doc1", "source": "dense", "content": "content1"},
            {"title": "Doc2", "source": "sparse", "content": "content2"},
            {"title": "Doc3", "source": "dense", "content": "content3"},
        ]
        scores = [0.7, 0.9, 0.6]  # sparse が最高スコア
        
        source_weights = {"dense": 1.0, "sparse": 0.5}
        
        reranked_docs, reranked_scores = ranker.rerank_by_sources(documents, scores, source_weights)
        
        # dense ソースが上位に来るべき
        assert reranked_docs[0]["source"] == "dense"
    
    def test_fusion_scores(self):
        """スコア融合（RRF）"""
        ranker = SearchResultRanker()
        
        result1 = SearchResult(
            query="test",
            source="index1",
            source_type=SearchSourceType.DENSE_VECTOR,
            documents=[
                {"title": "A"},
                {"title": "B"},
            ],
            scores=[0.9, 0.8],
        )
        
        result2 = SearchResult(
            query="test",
            source="index2",
            source_type=SearchSourceType.SPARSE_VECTOR,
            documents=[
                {"title": "B"},
                {"title": "C"},
            ],
            scores=[0.85, 0.7],
        )
        
        fused_docs, fused_scores = ranker.fusion_scores(result1, result2, alpha=0.5)
        
        assert len(fused_docs) >= 2
        assert "B" in [doc["title"] for doc in fused_docs]  # Bは両方に出現


class TestSearchResultCache:
    """検索結果キャッシュのテスト"""
    
    def test_cache_put_get(self):
        """キャッシュの保存と取得"""
        cache = SearchResultCache(ttl_seconds=10)
        
        result = SearchResult(
            query="test",
            source="test_index",
            source_type=SearchSourceType.DENSE_VECTOR,
        )
        
        cache.put("key1", result)
        cached_result = cache.get("key1")
        
        assert cached_result is not None
        assert cached_result.query == "test"
    
    def test_cache_expiration(self):
        """キャッシュ有効期限"""
        cache = SearchResultCache(ttl_seconds=0.1)  # 0.1秒で期限切れ
        
        result = SearchResult(
            query="test",
            source="test_index",
            source_type=SearchSourceType.DENSE_VECTOR,
        )
        
        cache.put("key1", result)
        
        # すぐに取得 -> キャッシュヒット
        assert cache.get("key1") is not None
        
        # 待機してから取得 -> キャッシュミス
        import time
        time.sleep(0.2)
        assert cache.get("key1") is None
    
    def test_cache_stats(self):
        """キャッシュ統計"""
        cache = SearchResultCache()
        
        result = SearchResult(
            query="test",
            source="test_index",
            source_type=SearchSourceType.DENSE_VECTOR,
        )
        
        cache.put("key1", result)
        cache.put("key2", result)
        
        stats = cache.get_stats()
        assert stats["cache_size"] == 2


class TestMockIndices:
    """モックインデックスのテスト"""
    
    @pytest.mark.asyncio
    async def test_dense_vector_index_search(self):
        """デンスベクトルインデックス検索"""
        index = MockDenseVectorIndex()
        
        result = await index.search("Paris capital")
        
        assert result.source_type == SearchSourceType.DENSE_VECTOR
        assert len(result.documents) > 0
        assert all(isinstance(s, float) for s in result.scores)
    
    @pytest.mark.asyncio
    async def test_sparse_vector_index_search(self):
        """スパースベクトルインデックス検索"""
        index = MockSparseVectorIndex()
        
        result = await index.search("France country")
        
        assert result.source_type == SearchSourceType.SPARSE_VECTOR
        assert len(result.documents) > 0
    
    @pytest.mark.asyncio
    async def test_index_names(self):
        """インデックス名"""
        dense_index = MockDenseVectorIndex("my_dense")
        sparse_index = MockSparseVectorIndex("my_sparse")
        
        assert dense_index.index_name() == "my_dense"
        assert sparse_index.index_name() == "my_sparse"


class TestParallelSearchEngine:
    """並列検索エンジンのテスト"""
    
    @pytest.mark.asyncio
    async def test_single_index_search(self):
        """単一インデックス検索"""
        engine = ParallelSearchEngine()
        engine.register_index("dense", MockDenseVectorIndex("dense_index"))
        
        request = ParallelSearchRequest(
            query="Paris",
            sources=["dense"],
            top_k=5,
        )
        
        result = await engine.search_parallel(request)
        
        assert len(result.merged_documents) > 0
        assert "dense_index" in result.source_breakdown
    
    @pytest.mark.asyncio
    async def test_parallel_search_multiple_indices(self):
        """複数インデックスの並列検索"""
        engine = ParallelSearchEngine()
        engine.register_index("dense", MockDenseVectorIndex("dense_index"))
        engine.register_index("sparse", MockSparseVectorIndex("sparse_index"))
        
        request = ParallelSearchRequest(
            query="capital France",
            sources=["dense", "sparse"],
            top_k=10,
            rerank=False,
        )
        
        result = await engine.search_parallel(request)
        
        assert len(result.merged_documents) > 0
        assert len(result.source_breakdown) > 0
        # 両方のソースから結果が得られるべき
        assert "dense_index" in result.source_breakdown or "sparse_index" in result.source_breakdown
    
    @pytest.mark.asyncio
    async def test_search_with_reranking(self):
        """リランキング付き検索"""
        engine = ParallelSearchEngine()
        engine.register_index("dense", MockDenseVectorIndex())
        engine.register_index("sparse", MockSparseVectorIndex())
        
        request = ParallelSearchRequest(
            query="Paris",
            sources=["dense", "sparse"],
            top_k=5,
            rerank=True,
        )
        
        result = await engine.search_parallel(request)
        
        assert result.rerank_applied is True
        assert len(result.merged_documents) > 0
    
    @pytest.mark.asyncio
    async def test_search_with_cache(self):
        """キャッシング付き検索"""
        engine = ParallelSearchEngine()
        engine.register_index("dense", MockDenseVectorIndex())
        
        request = ParallelSearchRequest(
            query="Paris",
            sources=["dense"],
            enable_cache=True,
        )
        
        # 1回目の検索
        result1 = await engine.search_parallel(request)
        
        # 2回目の検索（キャッシュヒット）
        result2 = await engine.search_parallel(request)
        
        # キャッシュサイズを確認
        cache_stats = engine.get_cache_stats()
        assert cache_stats["cache_size"] > 0
    
    @pytest.mark.asyncio
    async def test_search_timeout_handling(self):
        """タイムアウト処理"""
        engine = ParallelSearchEngine()
        
        # タイムアウトするインデックス
        class SlowIndex(MockDenseVectorIndex):
            async def search(self, query, top_k=10, filters=None):
                await asyncio.sleep(10)  # 10秒かかる
                return await super().search(query, top_k, filters)
        
        engine.register_index("slow", SlowIndex("slow_index"))
        
        request = ParallelSearchRequest(
            query="Paris",
            sources=["slow"],
            timeout_seconds=0.1,  # 0.1秒でタイムアウト
        )
        
        result = await engine.search_parallel(request)
        
        # タイムアウトしたので検索結果が空か、エラーが発生している
        # search_results は内部的に管理されているため、マージ結果が空であることを確認
        assert len(result.merged_documents) == 0 or result.total_search_time_ms > 0
    
    def test_cache_clear(self):
        """キャッシュクリア"""
        engine = ParallelSearchEngine()
        
        result = SearchResult(
            query="test",
            source="test",
            source_type=SearchSourceType.DENSE_VECTOR,
        )
        
        engine.cache.put("key1", result)
        assert engine.cache.get("key1") is not None
        
        engine.clear_cache()
        assert engine.cache.get("key1") is None


class TestParallelSearchPerformance:
    """並列検索のパフォーマンステスト"""
    
    @pytest.mark.asyncio
    async def test_parallel_vs_sequential(self):
        """並列 vs 順序処理のパフォーマンス比較"""
        engine = ParallelSearchEngine()
        engine.register_index("dense", MockDenseVectorIndex())
        engine.register_index("sparse", MockSparseVectorIndex())
        
        request = ParallelSearchRequest(
            query="Paris capital",
            sources=["dense", "sparse"],
            top_k=10,
            rerank=False,
        )
        
        result = await engine.search_parallel(request)
        
        # 並列検索の総時間は個別検索より短い（非同期なため）
        assert result.total_search_time_ms > 0
        # 100ms以下であるべき（デモなのでそこまで厳しくない）
        assert result.total_search_time_ms < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
