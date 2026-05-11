"""
RAG精度定量評価エンジン
Retrieval, Generation, 統合パイプラインの評価
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import math
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RetrievalMetricType(Enum):
    """検索メトリクスの種類"""
    PRECISION_AT_K = "precision_at_k"
    RECALL_AT_K = "recall_at_k"
    MRR = "mrr"  # Mean Reciprocal Rank
    NDCG = "ndcg"  # Normalized Discounted Cumulative Gain
    MAP = "map"  # Mean Average Precision
    HIT_RATE = "hit_rate"
    F1_SCORE = "f1_score"


@dataclass
class RetrievalResult:
    """検索結果"""
    query: str
    retrieved_documents: List[str]  # 検索されたドキュメントID
    retrieved_scores: List[float]  # 各ドキュメントのスコア
    relevant_documents: Set[str]  # 正解のドキュメントID
    rank_of_first_relevant: Optional[int] = None  # 最初の正解の順位
    
    def __post_init__(self):
        """初期化時に最初の正解の順位を計算"""
        for i, doc in enumerate(self.retrieved_documents):
            if doc in self.relevant_documents:
                self.rank_of_first_relevant = i + 1  # 1-indexed
                break


@dataclass
class RetrievalMetrics:
    """検索メトリクス"""
    precision_at_k: Dict[int, float] = field(default_factory=dict)  # {k: score}
    recall_at_k: Dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg_at_k: Dict[int, float] = field(default_factory=dict)
    map_score: float = 0.0
    hit_rate: float = 0.0
    f1_at_k: Dict[int, float] = field(default_factory=dict)
    
    def average_precision_at_k(self, k: int) -> float:
        """k における平均精度"""
        if k in self.precision_at_k:
            return self.precision_at_k[k]
        return 0.0


@dataclass
class GenerationQuality:
    """生成品質メトリクス"""
    rouge_score: float  # ROUGE-L
    bleu_score: float
    semantic_similarity: float  # コサイン類似度
    relevance_to_query: float
    factual_consistency: float  # 事実的一貫性
    answer_length: int
    coverage_ratio: float  # 検索結果のカバレッジ


@dataclass
class RAGEvaluationResult:
    """RAG全体評価結果"""
    query: str
    retrieved_documents: List[str]
    generated_answer: str
    ground_truth: str
    retrieval_metrics: RetrievalMetrics
    generation_quality: GenerationQuality
    end_to_end_score: float  # 0-1
    retrieval_contribution: float  # 検索が最終スコアに与える影響
    generation_contribution: float  # 生成が最終スコアに与える影響
    issues: List[str] = field(default_factory=list)


class RetrievalEvaluator:
    """検索評価器"""
    
    @staticmethod
    def precision_at_k(
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Precision@k = |relevant ∩ retrieved_k| / k
        """
        retrieved_k = set(retrieved[:k])
        if k == 0:
            return 0.0
        
        tp = len(relevant & retrieved_k)
        return tp / k
    
    @staticmethod
    def recall_at_k(
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Recall@k = |relevant ∩ retrieved_k| / |relevant|
        """
        retrieved_k = set(retrieved[:k])
        if len(relevant) == 0:
            return 0.0
        
        tp = len(relevant & retrieved_k)
        return tp / len(relevant)
    
    @staticmethod
    def mean_reciprocal_rank(result: RetrievalResult) -> float:
        """
        MRR = 1 / rank_of_first_relevant
        """
        if result.rank_of_first_relevant is None:
            return 0.0
        return 1.0 / result.rank_of_first_relevant
    
    @staticmethod
    def ndcg_at_k(
        retrieved: List[str],
        relevant: Set[str],
        k: int,
        scores: Optional[List[float]] = None
    ) -> float:
        """
        Normalized Discounted Cumulative Gain
        DCG = Σ (rel_i / log2(i+1)) for i=1 to k
        NDCG = DCG / IDCG
        """
        # DCG計算
        dcg = 0.0
        for i, doc in enumerate(retrieved[:k]):
            rel = 1.0 if doc in relevant else 0.0
            dcg += rel / math.log2(i + 2)  # i+2 because log2(1) = 0
        
        # IDCG計算（理想的なランキング）
        ideal_dcg = 0.0
        for i in range(min(k, len(relevant))):
            ideal_dcg += 1.0 / math.log2(i + 2)
        
        if ideal_dcg == 0:
            return 0.0
        
        return dcg / ideal_dcg
    
    @staticmethod
    def mean_average_precision(result: RetrievalResult) -> float:
        """
        MAP = Σ (P@k * rel_k) / |relevant|
        where rel_k = 1 if document at rank k is relevant
        """
        if len(result.relevant_documents) == 0:
            return 0.0
        
        ap = 0.0
        num_relevant_at_k = 0
        
        for k, doc in enumerate(result.retrieved_documents, 1):
            if doc in result.relevant_documents:
                num_relevant_at_k += 1
                precision_at_k = num_relevant_at_k / k
                ap += precision_at_k
        
        return ap / len(result.relevant_documents)
    
    @staticmethod
    def hit_rate(
        retrieved: List[str],
        relevant: Set[str]
    ) -> float:
        """
        Hit Rate = 1 if any relevant document in top-k, 0 otherwise
        """
        retrieved_set = set(retrieved)
        return 1.0 if len(relevant & retrieved_set) > 0 else 0.0
    
    def compute_all_metrics(
        self,
        result: RetrievalResult,
        k_values: List[int] = [1, 5, 10]
    ) -> RetrievalMetrics:
        """すべての検索メトリクスを計算"""
        metrics = RetrievalMetrics()
        
        # Precision/Recall @ k
        for k in k_values:
            metrics.precision_at_k[k] = self.precision_at_k(
                result.retrieved_documents,
                result.relevant_documents,
                k
            )
            metrics.recall_at_k[k] = self.recall_at_k(
                result.retrieved_documents,
                result.relevant_documents,
                k
            )
            
            # F1 Score
            p = metrics.precision_at_k[k]
            r = metrics.recall_at_k[k]
            if p + r > 0:
                f1 = 2 * (p * r) / (p + r)
            else:
                f1 = 0.0
            metrics.f1_at_k[k] = f1
            
            # NDCG
            metrics.ndcg_at_k[k] = self.ndcg_at_k(
                result.retrieved_documents,
                result.relevant_documents,
                k
            )
        
        # MRR
        metrics.mrr = self.mean_reciprocal_rank(result)
        
        # MAP
        metrics.map_score = self.mean_average_precision(result)
        
        # Hit Rate
        metrics.hit_rate = self.hit_rate(
            result.retrieved_documents,
            result.relevant_documents
        )
        
        return metrics


class GenerationEvaluator:
    """生成品質評価器"""
    
    @staticmethod
    def rouge_l_score(candidate: str, reference: str) -> float:
        """
        ROUGE-L スコア（簡略実装）
        共通部分文字列の長さ / 参照テキストの長さ
        """
        candidate_lower = candidate.lower()
        reference_lower = reference.lower()
        
        # LCS（最長共通部分列）を計算
        def lcs_length(s1: str, s2: str) -> int:
            m, n = len(s1), len(s2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i-1] == s2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                    else:
                        dp[i][j] = max(dp[i-1][j], dp[i][j-1])
            
            return dp[m][n]
        
        lcs_len = lcs_length(candidate_lower, reference_lower)
        return lcs_len / max(len(reference_lower), 1)
    
    @staticmethod
    def bleu_score(candidate: str, reference: str) -> float:
        """
        BLEU スコア（簡略実装）
        1-gram精度の平均
        """
        candidate_words = set(candidate.lower().split())
        reference_words = set(reference.lower().split())
        
        if len(reference_words) == 0:
            return 0.0
        
        overlap = len(candidate_words & reference_words)
        return overlap / len(reference_words)
    
    @staticmethod
    def semantic_similarity(candidate: str, reference: str) -> float:
        """
        意味的類似性（簡略実装：単語重複比率）
        """
        candidate_words = set(candidate.lower().split())
        reference_words = set(reference.lower().split())
        
        if len(candidate_words | reference_words) == 0:
            return 0.0
        
        jaccard = len(candidate_words & reference_words) / len(candidate_words | reference_words)
        return jaccard
    
    def compute_quality(
        self,
        generated_answer: str,
        ground_truth: str,
        query: str = "",
        retrieved_documents: List[str] = None,
    ) -> GenerationQuality:
        """生成品質を評価"""
        
        quality = GenerationQuality(
            rouge_score=self.rouge_l_score(generated_answer, ground_truth),
            bleu_score=self.bleu_score(generated_answer, ground_truth),
            semantic_similarity=self.semantic_similarity(generated_answer, ground_truth),
            relevance_to_query=self._compute_relevance_to_query(generated_answer, query),
            factual_consistency=self._compute_factual_consistency(generated_answer),
            answer_length=len(generated_answer.split()),
            coverage_ratio=self._compute_coverage_ratio(generated_answer, retrieved_documents or []),
        )
        
        return quality
    
    @staticmethod
    def _compute_relevance_to_query(answer: str, query: str) -> float:
        """クエリへの関連性を計算"""
        if not query:
            return 0.5
        
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        
        if len(query_words) == 0:
            return 0.0
        
        overlap = len(query_words & answer_words)
        return min(1.0, overlap / len(query_words))
    
    @staticmethod
    def _compute_factual_consistency(answer: str) -> float:
        """事実的一貫性を推定（簡略版）"""
        # デモ用：既知の不正確な表現をチェック
        false_patterns = [
            "is the capital of Germany",
            "is in China",
            "2+2=5",
        ]
        
        answer_lower = answer.lower()
        for pattern in false_patterns:
            if pattern in answer_lower:
                return 0.3  # 低信頼度
        
        return 0.8  # デフォルトで高信頼度
    
    @staticmethod
    def _compute_coverage_ratio(answer: str, retrieved_documents: List[str]) -> float:
        """検索結果のカバレッジ率"""
        if not retrieved_documents:
            return 0.0
        
        answer_lower = answer.lower()
        covered_docs = 0
        
        for doc in retrieved_documents:
            doc_lower = doc.lower()
            # ドキュメントの単語がanswer内に含まれているかチェック
            doc_words = set(doc_lower.split())
            answer_words = set(answer_lower.split())
            
            if len(doc_words & answer_words) > len(doc_words) * 0.3:
                covered_docs += 1
        
        return min(1.0, covered_docs / len(retrieved_documents))


class RAGEvaluator:
    """RAG全体評価器"""
    
    def __init__(self):
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator()
    
    def evaluate_rag_pipeline(
        self,
        query: str,
        retrieved_documents: List[str],
        retrieved_scores: List[float],
        generated_answer: str,
        ground_truth: str,
        relevant_documents: Set[str],
    ) -> RAGEvaluationResult:
        """RAGパイプライン全体を評価"""
        
        # 検索評価
        retrieval_result = RetrievalResult(
            query=query,
            retrieved_documents=retrieved_documents,
            retrieved_scores=retrieved_scores,
            relevant_documents=relevant_documents,
        )
        
        retrieval_metrics = self.retrieval_evaluator.compute_all_metrics(retrieval_result)
        
        # 生成品質評価
        generation_quality = self.generation_evaluator.compute_quality(
            generated_answer,
            ground_truth,
            query,
            retrieved_documents,
        )
        
        # 統合スコア計算
        retrieval_score = (
            retrieval_metrics.mrr * 0.3 +
            retrieval_metrics.map_score * 0.3 +
            retrieval_metrics.hit_rate * 0.2 +
            retrieval_metrics.ndcg_at_k.get(5, 0.0) * 0.2
        )
        
        generation_score = (
            generation_quality.rouge_score * 0.3 +
            generation_quality.bleu_score * 0.2 +
            generation_quality.semantic_similarity * 0.3 +
            generation_quality.relevance_to_query * 0.2
        )
        
        # 最終スコア
        end_to_end_score = retrieval_score * 0.4 + generation_score * 0.6
        
        # 問題を特定
        issues = []
        if retrieval_metrics.hit_rate < 0.5:
            issues.append("Low retrieval hit rate")
        if generation_quality.rouge_score < 0.3:
            issues.append("Low ROUGE score")
        if generation_quality.relevance_to_query < 0.5:
            issues.append("Low query relevance")
        
        return RAGEvaluationResult(
            query=query,
            retrieved_documents=retrieved_documents,
            generated_answer=generated_answer,
            ground_truth=ground_truth,
            retrieval_metrics=retrieval_metrics,
            generation_quality=generation_quality,
            end_to_end_score=end_to_end_score,
            retrieval_contribution=0.4,
            generation_contribution=0.6,
            issues=issues,
        )
    
    def batch_evaluate(
        self,
        evaluation_data: List[Dict],
    ) -> Dict:
        """
        バッチ評価
        evaluation_data: [
            {
                'query': str,
                'retrieved_documents': List[str],
                'retrieved_scores': List[float],
                'generated_answer': str,
                'ground_truth': str,
                'relevant_documents': Set[str],
            },
            ...
        ]
        """
        results = []
        aggregated_metrics = defaultdict(list)
        
        for data in evaluation_data:
            result = self.evaluate_rag_pipeline(**data)
            results.append(result)
            
            # メトリクス集約
            aggregated_metrics['end_to_end_score'].append(result.end_to_end_score)
            aggregated_metrics['mrr'].append(result.retrieval_metrics.mrr)
            aggregated_metrics['map'].append(result.retrieval_metrics.map_score)
            aggregated_metrics['rouge'].append(result.generation_quality.rouge_score)
            aggregated_metrics['bleu'].append(result.generation_quality.bleu_score)
        
        # 平均を計算
        average_metrics = {}
        for metric, values in aggregated_metrics.items():
            average_metrics[f"avg_{metric}"] = sum(values) / len(values) if values else 0.0
        
        return {
            "results": results,
            "average_metrics": average_metrics,
            "total_samples": len(results),
        }
