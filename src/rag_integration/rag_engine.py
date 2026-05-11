"""
Phase 17 Task 2: RAG (検索拡張生成) 統合エンジン
IDEAL_LLM_RESEARCH_REPORT に基づくハイブリッド検索・再ランキング・生成パイプライン

特徴:
- ハイブリッド検索: BM25 (キーワード) + Dense検索 (セマンティック)
- 多段階ランキング: 初期フィルタ → 中速ランキング → 高精度リランキング
- コンテキスト圧縮: 関連情報のフィルタリングと要約
- 引用追跡: 回答に対する参照源の記録
- 不確実性表現: 信頼度スコアと注釈

実装: 480行, テスト対応: 35個テスト想定
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from collections import defaultdict
import math


class RetrievalStrategy(Enum):
    """検索戦略"""
    KEYWORD = "keyword"  # BM25キーワード検索
    SEMANTIC = "semantic"  # Dense (埋め込み) 検索
    HYBRID = "hybrid"  # ハイブリッド検索


class RankingStrategy(Enum):
    """ランキング戦略"""
    FAST = "fast"  # 高速初期フィルタ
    MEDIUM = "medium"  # 中速ランキング
    PRECISION = "precision"  # 高精度リランキング


@dataclass
class Document:
    """ドキュメント"""
    doc_id: str
    title: str
    content: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """検索結果"""
    query: str
    documents: List[Document]
    retrieval_strategy: RetrievalStrategy
    ranking_strategy: RankingStrategy
    search_time_ms: float
    total_documents_searched: int


@dataclass
class GenerationResult:
    """生成結果"""
    query: str
    response: str
    source_documents: List[Document]
    confidence_score: float
    citations: List[Dict[str, str]]  # {text, source}
    uncertainty_notes: List[str]
    generation_time_ms: float


class KeywordSearchEngine:
    """BM25キーワード検索エンジン"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        BM25パラメータ初期化
        k1: 用語頻度の飽和パラメータ
        b: 文書長の正規化パラメータ
        """
        self.k1 = k1
        self.b = b
        self.documents = []
        self.idf_cache = {}

    def index_documents(self, documents: List[Document]) -> Dict:
        """ドキュメントをインデックス"""
        self.documents = documents
        self.idf_cache.clear()

        # IDF計算
        doc_count = len(documents)
        word_docs = defaultdict(int)

        for doc in documents:
            words = set(doc.content.lower().split())
            for word in words:
                word_docs[word] += 1

        for word, count in word_docs.items():
            self.idf_cache[word] = math.log((doc_count - count + 0.5) / (count + 0.5) + 1.0)

        return {
            "indexed_documents": len(documents),
            "vocabulary_size": len(self.idf_cache)
        }

    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """キーワード検索"""
        query_words = query.lower().split()
        scores = []

        avg_doc_len = sum(len(doc.content.split()) for doc in self.documents) / max(1, len(self.documents))

        for doc in self.documents:
            doc_words = doc.content.lower().split()
            doc_len = len(doc_words)
            score = 0.0

            for word in query_words:
                term_freq = doc_words.count(word)
                idf = self.idf_cache.get(word, 0.0)

                # BM25スコア計算
                numerator = idf * term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (1 - self.b + self.b * (doc_len / avg_doc_len))
                score += numerator / denominator

            scores.append((score, doc))

        # スコアでソート
        ranked = sorted(scores, key=lambda x: x[0], reverse=True)
        results = []

        for score, doc in ranked[:top_k]:
            doc.relevance_score = score
            results.append(doc)

        return results


class SemanticSearchEngine:
    """Dense検索エンジン (セマンティック)"""

    def __init__(self):
        self.documents = []
        self.embeddings = {}

    def index_documents(self, documents: List[Document]) -> Dict:
        """ドキュメントをインデックス"""
        self.documents = documents

        # ダミー埋め込み生成 (実装では外部モデルを使用)
        for doc in documents:
            # 簡易的なハッシュベース埋め込み
            embedding = self._generate_dummy_embedding(doc.content)
            self.embeddings[doc.doc_id] = embedding
            doc.embedding = embedding

        return {
            "indexed_documents": len(documents),
            "embedding_dim": len(self.embeddings[documents[0].doc_id]) if documents else 0
        }

    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """セマンティック検索"""
        query_embedding = self._generate_dummy_embedding(query)
        scores = []

        for doc in self.documents:
            if doc.doc_id not in self.embeddings:
                continue

            # コサイン類似度計算
            similarity = self._cosine_similarity(query_embedding, self.embeddings[doc.doc_id])
            scores.append((similarity, doc))

        ranked = sorted(scores, key=lambda x: x[0], reverse=True)
        results = []

        for score, doc in ranked[:top_k]:
            doc.relevance_score = score
            results.append(doc)

        return results

    def _generate_dummy_embedding(self, text: str) -> List[float]:
        """ダミー埋め込み生成"""
        # 実装では実際の埋め込みモデルを使用
        words = text.lower().split()
        embedding = [0.0] * 128
        for i, word in enumerate(words[:128]):
            embedding[i] = (ord(word[0]) / 255.0) if word else 0.0
        return embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """コサイン類似度計算"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x ** 2 for x in a))
        norm_b = math.sqrt(sum(x ** 2 for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class RerankerModule:
    """再ランキング (Reranker) モジュール"""

    def __init__(self):
        self.reranking_history = []

    def rerank(
        self,
        query: str,
        documents: List[Document],
        strategy: RankingStrategy = RankingStrategy.PRECISION
    ) -> List[Document]:
        """ドキュメントを再ランキング"""

        if strategy == RankingStrategy.FAST:
            reranked = self._fast_rerank(query, documents)
        elif strategy == RankingStrategy.MEDIUM:
            reranked = self._medium_rerank(query, documents)
        else:  # PRECISION
            reranked = self._precision_rerank(query, documents)

        self.reranking_history.append({
            "query": query,
            "strategy": strategy.value,
            "input_count": len(documents),
            "output_count": len(reranked),
            "timestamp": datetime.now().isoformat()
        })

        return reranked

    def _fast_rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """高速初期フィルタ"""
        # クエリワードとの一致度でフィルタ
        query_words = set(query.lower().split())
        scored = []

        for doc in documents:
            doc_words = set(doc.content.lower().split())
            match_count = len(query_words & doc_words)
            scored.append((match_count, doc))

        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]

    def _medium_rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """中速ランキング"""
        # タイトル + コンテンツでスコア計算
        scored = []

        for doc in documents:
            title_matches = sum(1 for word in query.lower().split() if word in doc.title.lower())
            content_matches = sum(1 for word in query.lower().split() if word in doc.content.lower())
            score = title_matches * 2 + content_matches
            scored.append((score, doc))

        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]

    def _precision_rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """高精度リランキング (交差符号化)"""
        # 複合スコア計算
        scored = []

        for doc in documents:
            relevance = doc.relevance_score if doc.relevance_score > 0 else 0.5

            # 文書の長さが適切か判定
            length_score = min(1.0, len(doc.content.split()) / 200.0)

            # ソースの信頼度 (メタデータから)
            source_score = 0.9 if "trusted" in doc.metadata.get("type", "").lower() else 0.7

            # 複合スコア
            combined_score = (relevance * 0.5) + (length_score * 0.3) + (source_score * 0.2)
            scored.append((combined_score, doc))

        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]


class ContextCompressor:
    """コンテキスト圧縮モジュール"""

    def compress(
        self,
        documents: List[Document],
        max_tokens: int = 2000
    ) -> Tuple[str, List[Document]]:
        """ドキュメントをコンテキスト長に圧縮"""

        compressed_context = ""
        selected_docs = []
        token_count = 0

        for doc in documents:
            doc_tokens = len(doc.content.split())

            if token_count + doc_tokens <= max_tokens:
                # タイトル + サマリー
                doc_summary = f"\n[{doc.title}]\n{doc.content[:500]}..."
                compressed_context += doc_summary
                token_count += doc_tokens
                selected_docs.append(doc)
            else:
                # トークン制限に達した
                break

        return compressed_context, selected_docs

    def extract_key_phrases(self, text: str, top_k: int = 5) -> List[str]:
        """重要フレーズ抽出"""
        # 簡易的なフレーズ抽出
        words = text.lower().split()
        phrase_freq = defaultdict(int)

        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if len(words[i]) > 3 and len(words[i+1]) > 3:
                phrase_freq[phrase] += 1

        sorted_phrases = sorted(phrase_freq.items(), key=lambda x: x[1], reverse=True)
        return [phrase for phrase, _ in sorted_phrases[:top_k]]


class CitationTracker:
    """引用追跡モジュール"""

    def __init__(self):
        self.citations = []

    def extract_citations(
        self,
        response: str,
        source_documents: List[Document]
    ) -> List[Dict[str, str]]:
        """応答から引用を抽出"""
        citations = []

        for doc in source_documents:
            # ドキュメント内容の断片が応答に含まれているか確認
            key_phrases = self._get_key_phrases(doc.content)

            for phrase in key_phrases:
                if phrase.lower() in response.lower():
                    citations.append({
                        "text": phrase,
                        "source": doc.source,
                        "doc_id": doc.doc_id,
                        "title": doc.title
                    })

        return citations

    def _get_key_phrases(self, text: str, count: int = 3) -> List[str]:
        """テキストから主要フレーズを抽出"""
        sentences = text.split(".")
        return [sent.strip()[:50] for sent in sentences[:count] if sent.strip()]

    def generate_bibliography(self, citations: List[Dict[str, str]]) -> str:
        """参考文献リストを生成"""
        bibliography = "\n## 参考文献\n"

        for i, citation in enumerate(set(c["source"] for c in citations), 1):
            bibliography += f"{i}. {citation}\n"

        return bibliography


class RAGEngine:
    """
    統合RAG (検索拡張生成) エンジン
    IDEAL_LLM_RESEARCH_REPORT のハイブリッド検索・再ランキング・生成パイプライン
    """

    def __init__(self):
        self.keyword_engine = KeywordSearchEngine()
        self.semantic_engine = SemanticSearchEngine()
        self.reranker = RerankerModule()
        self.compressor = ContextCompressor()
        self.citation_tracker = CitationTracker()
        self.documents = []
        self.rag_history = []

    def build_index(self, documents: List[Document]) -> Dict:
        """ドキュメントベースのインデックス構築"""
        self.documents = documents

        # 両方の検索エンジンでインデックス
        keyword_stats = self.keyword_engine.index_documents(documents)
        semantic_stats = self.semantic_engine.index_documents(documents)

        return {
            "keyword_index": keyword_stats,
            "semantic_index": semantic_stats,
            "total_documents": len(documents)
        }

    def retrieve(
        self,
        query: str,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        top_k: int = 5,
        ranking_strategy: RankingStrategy = RankingStrategy.PRECISION
    ) -> RetrievalResult:
        """ドキュメント検索"""

        start_time = datetime.now()

        if strategy == RetrievalStrategy.KEYWORD:
            documents = self.keyword_engine.search(query, top_k)
        elif strategy == RetrievalStrategy.SEMANTIC:
            documents = self.semantic_engine.search(query, top_k)
        else:  # HYBRID
            keyword_docs = self.keyword_engine.search(query, top_k)
            semantic_docs = self.semantic_engine.search(query, top_k)

            # ハイブリッド結果のマージ (スコアの重み付け)
            merged = {}
            for doc in keyword_docs:
                merged[doc.doc_id] = doc.relevance_score * 0.5

            for doc in semantic_docs:
                if doc.doc_id in merged:
                    merged[doc.doc_id] += doc.relevance_score * 0.5
                else:
                    merged[doc.doc_id] = doc.relevance_score * 0.5

            # スコアでソート
            sorted_docs = sorted(merged.items(), key=lambda x: x[1], reverse=True)
            documents = [self._find_document(doc_id) for doc_id, _ in sorted_docs[:top_k]]

        # 再ランキング
        reranked = self.reranker.rerank(query, documents, ranking_strategy)

        search_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        result = RetrievalResult(
            query=query,
            documents=reranked,
            retrieval_strategy=strategy,
            ranking_strategy=ranking_strategy,
            search_time_ms=search_time_ms,
            total_documents_searched=len(self.documents)
        )

        return result

    def generate(
        self,
        query: str,
        generation_fn=None,
        retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    ) -> GenerationResult:
        """検索と生成を組み合わせたRAG"""

        # 検索
        retrieval_result = self.retrieve(query, retrieval_strategy)
        source_documents = retrieval_result.documents

        # コンテキスト圧縮
        context, compressed_docs = self.compressor.compress(source_documents)

        # 生成 (外部生成関数を使用)
        if generation_fn is None:
            response = self._default_generation(query, context)
        else:
            response = generation_fn(query, context)

        # 引用抽出
        citations = self.citation_tracker.extract_citations(response, compressed_docs)

        # 不確実性表現
        uncertainty_notes = self._generate_uncertainty_notes(retrieval_result)

        # 信頼度スコア計算
        confidence = self._calculate_confidence(retrieval_result)

        result = GenerationResult(
            query=query,
            response=response,
            source_documents=compressed_docs,
            confidence_score=confidence,
            citations=citations,
            uncertainty_notes=uncertainty_notes,
            generation_time_ms=retrieval_result.search_time_ms
        )

        self.rag_history.append({
            "query": query,
            "response": response,
            "confidence": confidence,
            "sources": len(compressed_docs),
            "timestamp": datetime.now().isoformat()
        })

        return result

    def _find_document(self, doc_id: str) -> Optional[Document]:
        """ドキュメントIDから該当ドキュメントを検索"""
        for doc in self.documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def _default_generation(self, query: str, context: str) -> str:
        """デフォルト生成 (簡易版)"""
        return f"クエリ: {query}\nコンテキスト: {context[:200]}..."

    def _generate_uncertainty_notes(self, retrieval_result: RetrievalResult) -> List[str]:
        """不確実性表現を生成"""
        notes = []

        if retrieval_result.search_time_ms > 1000:
            notes.append("検索に時間がかかりました。結果の完全性が保証されていない可能性があります。")

        if len(retrieval_result.documents) == 0:
            notes.append("関連ドキュメントが見つかりませんでした。回答の精度が低い可能性があります。")
        elif len(retrieval_result.documents) < 3:
            notes.append("参考資料が限定的です。追加情報の確認をお勧めします。")

        return notes

    def _calculate_confidence(self, retrieval_result: RetrievalResult) -> float:
        """信頼度スコアを計算"""
        if len(retrieval_result.documents) == 0:
            return 0.3

        avg_relevance = sum(doc.relevance_score for doc in retrieval_result.documents) / len(retrieval_result.documents)

        # スコア正規化
        confidence = min(1.0, avg_relevance * 0.9)

        return confidence

    def get_rag_statistics(self) -> Dict:
        """RAG統計"""
        if not self.rag_history:
            return {"total_queries": 0}

        total_queries = len(self.rag_history)
        avg_confidence = sum(r["confidence"] for r in self.rag_history) / total_queries
        avg_sources = sum(r["sources"] for r in self.rag_history) / total_queries

        return {
            "total_queries": total_queries,
            "avg_confidence": avg_confidence,
            "avg_sources_per_query": avg_sources,
            "last_query": self.rag_history[-1]["query"] if self.rag_history else None
        }
