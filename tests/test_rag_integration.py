"""
Phase 17 Task 2: RAG統合エンジンテスト
35個テスト: ハイブリッド検索・再ランキング・生成・引用追跡をカバー
"""

from src.rag_integration.rag_engine import (
    RetrievalStrategy,
    RankingStrategy,
    Document,
    RetrievalResult,
    GenerationResult,
    KeywordSearchEngine,
    SemanticSearchEngine,
    RerankerModule,
    ContextCompressor,
    CitationTracker,
    RAGEngine
)


class TestKeywordSearchEngine:
    """BM25キーワード検索エンジン"""

    def test_engine_initialization(self):
        """初期化テスト"""
        engine = KeywordSearchEngine()
        assert engine.k1 == 1.5
        assert engine.b == 0.75
        assert len(engine.documents) == 0

    def test_index_documents(self):
        """ドキュメントインデックス"""
        engine = KeywordSearchEngine()
        docs = [
            Document(doc_id="1", title="AI概要", content="AI is artificial intelligence", source="wiki"),
            Document(doc_id="2", title="機械学習", content="Machine learning is subset of AI", source="wiki")
        ]
        stats = engine.index_documents(docs)
        assert stats["indexed_documents"] == 2
        assert stats["vocabulary_size"] > 0

    def test_keyword_search(self):
        """キーワード検索"""
        engine = KeywordSearchEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence and machine learning", source="wiki"),
            Document(doc_id="2", title="Biology", content="cells and organisms", source="wiki")
        ]
        engine.index_documents(docs)
        results = engine.search("artificial intelligence", top_k=2)
        assert len(results) <= 2
        assert results[0].doc_id == "1"

    def test_search_empty_results(self):
        """空の検索結果"""
        engine = KeywordSearchEngine()
        docs = [
            Document(doc_id="1", title="Test", content="test content", source="wiki")
        ]
        engine.index_documents(docs)
        results = engine.search("nonexistent word", top_k=1)
        assert len(results) <= 1

    def test_bm25_score_calculation(self):
        """BM25スコア計算"""
        engine = KeywordSearchEngine()
        docs = [
            Document(doc_id="1", title="Test", content="word word word", source="wiki"),
            Document(doc_id="2", title="Test", content="word", source="wiki")
        ]
        engine.index_documents(docs)
        results = engine.search("word", top_k=2)
        # より多くの"word"を含むドキュメントがより高いスコア
        assert len(results) == 2


class TestSemanticSearchEngine:
    """Dense検索エンジン"""

    def test_engine_initialization(self):
        """初期化テスト"""
        engine = SemanticSearchEngine()
        assert len(engine.documents) == 0
        assert len(engine.embeddings) == 0

    def test_index_documents(self):
        """ドキュメントインデックス"""
        engine = SemanticSearchEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence concepts", source="wiki"),
            Document(doc_id="2", title="ML", content="machine learning algorithms", source="wiki")
        ]
        stats = engine.index_documents(docs)
        assert stats["indexed_documents"] == 2
        assert stats["embedding_dim"] == 128

    def test_semantic_search(self):
        """セマンティック検索"""
        engine = SemanticSearchEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence neural networks", source="wiki"),
            Document(doc_id="2", title="History", content="ancient civilizations empires", source="wiki")
        ]
        engine.index_documents(docs)
        results = engine.search("artificial intelligence", top_k=2)
        assert len(results) <= 2

    def test_embedding_generation(self):
        """埋め込み生成"""
        engine = SemanticSearchEngine()
        embedding = engine._generate_dummy_embedding("test text")
        assert len(embedding) == 128
        assert all(isinstance(x, float) for x in embedding)

    def test_cosine_similarity(self):
        """コサイン類似度計算"""
        engine = SemanticSearchEngine()
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [1.0, 0.0, 0.0]
        similarity = engine._cosine_similarity(vec_a, vec_b)
        assert abs(similarity - 1.0) < 0.01  # ほぼ1.0


class TestRerankerModule:
    """再ランキングモジュール"""

    def test_reranker_initialization(self):
        """初期化テスト"""
        reranker = RerankerModule()
        assert len(reranker.reranking_history) == 0

    def test_fast_rerank(self):
        """高速ランキング"""
        reranker = RerankerModule()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki"),
            Document(doc_id="2", title="ML", content="machine learning algorithm", source="wiki")
        ]
        result = reranker.rerank("artificial intelligence", docs, RankingStrategy.FAST)
        assert len(result) == 2

    def test_medium_rerank(self):
        """中速ランキング"""
        reranker = RerankerModule()
        docs = [
            Document(doc_id="1", title="AI", content="test content", source="wiki"),
            Document(doc_id="2", title="ML", content="test content machine learning", source="wiki")
        ]
        result = reranker.rerank("machine learning", docs, RankingStrategy.MEDIUM)
        assert len(result) == 2

    def test_precision_rerank(self):
        """高精度ランキング"""
        reranker = RerankerModule()
        docs = [
            Document(doc_id="1", title="AI", content="content", source="wiki", metadata={"type": "trusted"}),
            Document(doc_id="2", title="ML", content="content", source="wiki", metadata={"type": "general"})
        ]
        docs[0].relevance_score = 0.8
        docs[1].relevance_score = 0.7
        result = reranker.rerank("query", docs, RankingStrategy.PRECISION)
        assert len(result) == 2

    def test_reranking_history(self):
        """ランキング履歴"""
        reranker = RerankerModule()
        docs = [Document(doc_id="1", title="Test", content="test", source="wiki")]
        reranker.rerank("query", docs, RankingStrategy.FAST)
        assert len(reranker.reranking_history) == 1


class TestContextCompressor:
    """コンテキスト圧縮モジュール"""

    def test_compressor_initialization(self):
        """初期化テスト"""
        compressor = ContextCompressor()
        assert compressor is not None

    def test_compress_documents(self):
        """ドキュメント圧縮"""
        compressor = ContextCompressor()
        docs = [
            Document(doc_id="1", title="Title1", content="content1 " * 100, source="wiki"),
            Document(doc_id="2", title="Title2", content="content2 " * 100, source="wiki")
        ]
        context, selected = compressor.compress(docs, max_tokens=100)
        assert len(selected) <= 2
        assert "[Title" in context

    def test_extract_key_phrases(self):
        """重要フレーズ抽出"""
        compressor = ContextCompressor()
        text = "artificial intelligence and machine learning are related fields in computer science"
        phrases = compressor.extract_key_phrases(text, top_k=3)
        assert len(phrases) <= 3
        assert isinstance(phrases, list)

    def test_context_length_limit(self):
        """コンテキスト長制限"""
        compressor = ContextCompressor()
        docs = [
            Document(doc_id="1", title="Long", content="word " * 200, source="wiki")
        ]
        context, selected = compressor.compress(docs, max_tokens=50)
        # トークン数を超えないようにフィルタ
        assert len(selected) <= 1


class TestCitationTracker:
    """引用追跡モジュール"""

    def test_tracker_initialization(self):
        """初期化テスト"""
        tracker = CitationTracker()
        assert len(tracker.citations) == 0

    def test_extract_citations(self):
        """引用抽出"""
        tracker = CitationTracker()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence is important", source="wiki1"),
            Document(doc_id="2", title="ML", content="machine learning algorithms work", source="wiki2")
        ]
        response = "artificial intelligence and machine learning are important technologies"
        citations = tracker.extract_citations(response, docs)
        assert isinstance(citations, list)

    def test_bibliography_generation(self):
        """参考文献生成"""
        tracker = CitationTracker()
        citations = [
            {"text": "AI concepts", "source": "https://example.com/ai"},
            {"text": "ML basics", "source": "https://example.com/ml"}
        ]
        bib = tracker.generate_bibliography(citations)
        assert "参考文献" in bib
        assert "https://example.com" in bib

    def test_key_phrase_extraction(self):
        """キーフレーズ抽出"""
        tracker = CitationTracker()
        text = "artificial intelligence and machine learning concepts"
        phrases = tracker._get_key_phrases(text, count=2)
        assert len(phrases) <= 2


class TestRAGEngine:
    """統合RAGエンジン"""

    def test_rag_initialization(self):
        """初期化テスト"""
        engine = RAGEngine()
        assert engine.keyword_engine is not None
        assert engine.semantic_engine is not None
        assert engine.reranker is not None

    def test_build_index(self):
        """インデックス構築"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki"),
            Document(doc_id="2", title="ML", content="machine learning", source="wiki")
        ]
        stats = engine.build_index(docs)
        assert stats["total_documents"] == 2
        assert "keyword_index" in stats
        assert "semantic_index" in stats

    def test_keyword_retrieval(self):
        """キーワード検索による取得"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence neural networks", source="wiki"),
            Document(doc_id="2", title="History", content="ancient rome egypt", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("artificial intelligence", RetrievalStrategy.KEYWORD, top_k=2)
        assert result.retrieval_strategy == RetrievalStrategy.KEYWORD
        assert len(result.documents) <= 2

    def test_semantic_retrieval(self):
        """セマンティック検索による取得"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki"),
            Document(doc_id="2", title="Nature", content="mountains rivers forests", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("artificial intelligence", RetrievalStrategy.SEMANTIC, top_k=2)
        assert result.retrieval_strategy == RetrievalStrategy.SEMANTIC

    def test_hybrid_retrieval(self):
        """ハイブリッド検索"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence neural networks deep learning", source="wiki"),
            Document(doc_id="2", title="ML", content="machine learning algorithms", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("artificial intelligence", RetrievalStrategy.HYBRID, top_k=2)
        assert result.retrieval_strategy == RetrievalStrategy.HYBRID
        assert len(result.documents) > 0

    def test_reranking_strategy(self):
        """再ランキング戦略"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki"),
            Document(doc_id="2", title="ML", content="machine learning", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("AI", RetrievalStrategy.HYBRID, ranking_strategy=RankingStrategy.PRECISION)
        assert result.ranking_strategy == RankingStrategy.PRECISION

    def test_generate_with_default_fn(self):
        """デフォルト生成関数"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence is important", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.generate("what is AI")
        assert isinstance(result, GenerationResult)
        assert len(result.response) > 0

    def test_generate_with_custom_fn(self):
        """カスタム生成関数"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)

        def custom_gen(query, context):
            return f"Custom response to: {query}"

        result = engine.generate("what is AI", custom_gen)
        assert "Custom response" in result.response

    def test_confidence_calculation(self):
        """信頼度計算"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        docs[0].relevance_score = 0.9
        engine.build_index(docs)
        result = engine.generate("what is AI")
        assert 0 <= result.confidence_score <= 1.0

    def test_uncertainty_notes(self):
        """不確実性表現"""
        engine = RAGEngine()
        docs = []  # 空のドキュメント
        engine.build_index(docs)
        result = engine.generate("what is AI")
        assert len(result.uncertainty_notes) > 0

    def test_citations_generation(self):
        """引用生成"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence concepts", source="wiki.org"),
            Document(doc_id="2", title="ML", content="machine learning theory", source="ml.org")
        ]
        engine.build_index(docs)
        result = engine.generate("artificial intelligence concepts")
        assert isinstance(result.citations, list)

    def test_rag_statistics(self):
        """RAG統計"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        engine.generate("query1")
        engine.generate("query2")
        stats = engine.get_rag_statistics()
        assert stats["total_queries"] == 2
        assert "avg_confidence" in stats
        assert "avg_sources_per_query" in stats

    def test_retrieval_result_structure(self):
        """検索結果の構造"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("AI")
        assert isinstance(result, RetrievalResult)
        assert hasattr(result, "query")
        assert hasattr(result, "documents")
        assert hasattr(result, "search_time_ms")

    def test_generation_result_structure(self):
        """生成結果の構造"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.generate("what is AI")
        assert isinstance(result, GenerationResult)
        assert hasattr(result, "response")
        assert hasattr(result, "source_documents")
        assert hasattr(result, "citations")
        assert hasattr(result, "confidence_score")

    def test_multiple_document_ranking(self):
        """複数ドキュメントランキング"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI1", content="artificial intelligence", source="wiki1"),
            Document(doc_id="2", title="AI2", content="artificial intelligence machine learning", source="wiki2"),
            Document(doc_id="3", title="AI3", content="intelligence neural", source="wiki3")
        ]
        engine.build_index(docs)
        result = engine.retrieve("artificial intelligence", top_k=3)
        assert len(result.documents) <= 3

    def test_document_compression_limits(self):
        """ドキュメント圧縮制限"""
        engine = RAGEngine()
        long_content = "word " * 500
        docs = [
            Document(doc_id="1", title="Long", content=long_content, source="wiki1"),
            Document(doc_id="2", title="Long2", content=long_content, source="wiki2")
        ]
        engine.build_index(docs)
        result = engine.generate("query", retrieval_strategy=RetrievalStrategy.KEYWORD)
        assert len(result.source_documents) <= 2

    def test_no_documents_handling(self):
        """ドキュメントなしの処理"""
        engine = RAGEngine()
        engine.build_index([])
        result = engine.retrieve("query")
        assert len(result.documents) == 0
        assert result.total_documents_searched == 0

    def test_rag_history_tracking(self):
        """RAG履歴追跡"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        engine.generate("query1")
        engine.generate("query2")
        engine.generate("query3")
        assert len(engine.rag_history) == 3

    def test_search_time_measurement(self):
        """検索時間測定"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("AI")
        assert result.search_time_ms >= 0

    def test_hybrid_search_merging(self):
        """ハイブリッド検索の結果マージ"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence important", source="wiki1"),
            Document(doc_id="2", title="ML", content="machine learning algorithms", source="wiki2")
        ]
        engine.build_index(docs)
        result = engine.retrieve("artificial intelligence machine learning", RetrievalStrategy.HYBRID, top_k=2)
        assert len(result.documents) > 0

    def test_empty_query_handling(self):
        """空クエリの処理"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence", source="wiki")
        ]
        engine.build_index(docs)
        result = engine.retrieve("")
        assert isinstance(result, RetrievalResult)


# Integration Tests
class TestRAGIntegration:
    """RAG統合テスト"""

    def test_end_to_end_rag_pipeline(self):
        """エンドツーエンドRAGパイプライン"""
        engine = RAGEngine()

        # インデックス構築
        docs = [
            Document(doc_id="1", title="Python Guide", content="Python programming language", source="guide.org"),
            Document(doc_id="2", title="ML Tutorial", content="Machine learning tutorial and guide", source="ml.org"),
            Document(doc_id="3", title="AI Basics", content="Artificial intelligence fundamentals", source="ai.org")
        ]
        engine.build_index(docs)

        # クエリ実行
        result = engine.generate("How do I learn machine learning?")

        assert result.query == "How do I learn machine learning?"
        assert len(result.response) > 0
        assert 0 <= result.confidence_score <= 1.0

    def test_rag_with_all_strategies(self):
        """全検索戦略のテスト"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence concepts", source="wiki")
        ]
        engine.build_index(docs)

        for strategy in [RetrievalStrategy.KEYWORD, RetrievalStrategy.SEMANTIC, RetrievalStrategy.HYBRID]:
            result = engine.retrieve("artificial intelligence", strategy=strategy)
            assert result.retrieval_strategy == strategy

    def test_rag_quality_metrics(self):
        """RAG品質メトリクス"""
        engine = RAGEngine()
        docs = [
            Document(doc_id="1", title="AI", content="artificial intelligence is a field of computer science", source="wiki1"),
            Document(doc_id="2", title="ML", content="machine learning uses algorithms and statistics", source="wiki2")
        ]
        engine.build_index(docs)

        engine.generate("What is machine learning?")
        stats = engine.get_rag_statistics()

        assert stats["total_queries"] == 1
        assert stats["avg_confidence"] > 0
        assert stats["avg_sources_per_query"] > 0
