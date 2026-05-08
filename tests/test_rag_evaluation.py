"""
RAG評価エンジン テストスイート
"""

import pytest
from src.evaluation.rag_evaluation import (
    RetrievalEvaluator, GenerationEvaluator, RAGEvaluator,
    RetrievalResult, RetrievalMetrics
)


class TestRetrievalEvaluator:
    """検索評価器のテスト"""
    
    def test_precision_at_k(self):
        """Precision@k の計算"""
        evaluator = RetrievalEvaluator()
        
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3"}
        
        p_at_1 = evaluator.precision_at_k(retrieved, relevant, 1)
        p_at_3 = evaluator.precision_at_k(retrieved, relevant, 3)
        p_at_5 = evaluator.precision_at_k(retrieved, relevant, 5)
        
        assert p_at_1 == 1.0  # doc1 is relevant
        assert p_at_3 == 2/3  # doc1, doc3 are relevant
        assert p_at_5 == 2/5  # doc1, doc3 are relevant
    
    def test_recall_at_k(self):
        """Recall@k の計算"""
        evaluator = RetrievalEvaluator()
        
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3", "doc5"}
        
        r_at_3 = evaluator.recall_at_k(retrieved, relevant, 3)
        r_at_5 = evaluator.recall_at_k(retrieved, relevant, 5)
        
        assert r_at_3 == 2/3  # 2 out of 3 relevant docs retrieved
        assert r_at_5 == 3/3  # all 3 relevant docs retrieved
    
    def test_mrr(self):
        """Mean Reciprocal Rank の計算"""
        evaluator = RetrievalEvaluator()
        
        # 最初の関連文書が位置3にある場合
        result = RetrievalResult(
            query="test",
            retrieved_documents=["doc2", "doc4", "doc1", "doc3"],
            retrieved_scores=[0.9, 0.8, 0.7, 0.6],
            relevant_documents={"doc1", "doc3"},
        )
        
        mrr = evaluator.mean_reciprocal_rank(result)
        assert mrr == 1/3  # 最初の関連文書が位置3
    
    def test_ndcg_at_k(self):
        """NDCG@k の計算"""
        evaluator = RetrievalEvaluator()
        
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc3"}
        
        ndcg_at_3 = evaluator.ndcg_at_k(retrieved, relevant, 3)
        
        assert 0.0 <= ndcg_at_3 <= 1.0
        assert ndcg_at_3 > 0.5  # doc1は位置1（最高）、doc3は位置3
    
    def test_map(self):
        """Mean Average Precision の計算"""
        evaluator = RetrievalEvaluator()
        
        result = RetrievalResult(
            query="test",
            retrieved_documents=["doc1", "doc2", "doc3", "doc4", "doc5"],
            retrieved_scores=[0.9, 0.8, 0.7, 0.6, 0.5],
            relevant_documents={"doc1", "doc3"},
        )
        
        map_score = evaluator.mean_average_precision(result)
        
        # AP = (1/1 + 2/3) / 2 = (1 + 0.667) / 2 = 0.833
        assert 0.8 < map_score < 0.85
    
    def test_hit_rate(self):
        """Hit Rate の計算"""
        evaluator = RetrievalEvaluator()
        
        # 関連文書あり
        retrieved_with_relevant = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc4"}
        
        hit = evaluator.hit_rate(retrieved_with_relevant, relevant)
        assert hit == 1.0
        
        # 関連文書なし
        retrieved_no_relevant = ["doc2", "doc3", "doc5"]
        hit = evaluator.hit_rate(retrieved_no_relevant, relevant)
        assert hit == 0.0
    
    def test_compute_all_metrics(self):
        """すべてのメトリクスの計算"""
        evaluator = RetrievalEvaluator()
        
        result = RetrievalResult(
            query="test",
            retrieved_documents=["doc1", "doc2", "doc3", "doc4", "doc5"],
            retrieved_scores=[0.95, 0.85, 0.75, 0.65, 0.55],
            relevant_documents={"doc1", "doc3"},
        )
        
        metrics = evaluator.compute_all_metrics(result, k_values=[1, 3, 5])
        
        assert metrics.precision_at_k[1] == 1.0
        assert metrics.recall_at_k[5] > 0.0
        assert 0.0 <= metrics.mrr <= 1.0
        assert 0.0 <= metrics.map_score <= 1.0
        assert metrics.hit_rate == 1.0


class TestGenerationEvaluator:
    """生成品質評価器のテスト"""
    
    def test_rouge_l_score(self):
        """ROUGE-L スコア計算"""
        evaluator = GenerationEvaluator()
        
        candidate = "Paris is the capital of France"
        reference = "Paris is the capital of France"
        
        score = evaluator.rouge_l_score(candidate, reference)
        assert score > 0.8  # 高い一致度
    
    def test_bleu_score(self):
        """BLEU スコア計算"""
        evaluator = GenerationEvaluator()
        
        candidate = "Paris is the capital of France"
        reference = "Paris is the capital of France"
        
        score = evaluator.bleu_score(candidate, reference)
        assert score > 0.8
    
    def test_semantic_similarity(self):
        """意味的類似性計算"""
        evaluator = GenerationEvaluator()
        
        candidate = "Paris is the capital of France"
        reference = "The capital of France is Paris"
        
        score = evaluator.semantic_similarity(candidate, reference)
        assert 0.6 <= score <= 1.0  # 高い類似性
    
    def test_compute_quality(self):
        """生成品質評価"""
        evaluator = GenerationEvaluator()
        
        quality = evaluator.compute_quality(
            "Paris is the capital of France",
            "Paris is the capital of France",
            "What is the capital of France?",
        )
        
        assert quality.rouge_score > 0.8
        assert quality.bleu_score > 0.8
        assert quality.relevance_to_query > 0.5
        assert quality.answer_length > 0


class TestRAGEvaluator:
    """RAG全体評価器のテスト"""
    
    def test_evaluate_rag_pipeline(self):
        """RAGパイプライン評価"""
        evaluator = RAGEvaluator()
        
        result = evaluator.evaluate_rag_pipeline(
            query="What is the capital of France?",
            retrieved_documents=["doc1: Paris is in France", "doc2: Tokyo is in Japan"],
            retrieved_scores=[0.95, 0.70],
            generated_answer="Paris is the capital of France",
            ground_truth="Paris is the capital of France",
            relevant_documents={"doc1: Paris is in France"},
        )
        
        assert 0.0 <= result.end_to_end_score <= 1.0
        assert result.retrieval_metrics.hit_rate == 1.0
        assert result.generation_quality.rouge_score > 0.8
        assert result.retrieval_contribution == 0.4
        assert result.generation_contribution == 0.6
    
    def test_batch_evaluate(self):
        """バッチ評価"""
        evaluator = RAGEvaluator()
        
        evaluation_data = [
            {
                'query': 'What is the capital of France?',
                'retrieved_documents': ['doc1', 'doc2'],
                'retrieved_scores': [0.95, 0.70],
                'generated_answer': 'Paris is the capital of France',
                'ground_truth': 'Paris is the capital of France',
                'relevant_documents': {'doc1'},
            },
            {
                'query': 'What is the capital of Japan?',
                'retrieved_documents': ['doc3', 'doc4'],
                'retrieved_scores': [0.92, 0.68],
                'generated_answer': 'Tokyo is the capital of Japan',
                'ground_truth': 'Tokyo is the capital of Japan',
                'relevant_documents': {'doc3'},
            },
        ]
        
        results = evaluator.batch_evaluate(evaluation_data)
        
        assert results['total_samples'] == 2
        assert 'average_metrics' in results
        assert 'avg_end_to_end_score' in results['average_metrics']
        assert 0.0 <= results['average_metrics']['avg_end_to_end_score'] <= 1.0


class TestRAGEvaluationIntegration:
    """RAG評価統合テスト"""
    
    def test_rag_vs_naive_retrieval(self):
        """RAG と単純検索の比較"""
        evaluator = RAGEvaluator()
        
        # シナリオ1: 検索は成功だが生成品質が低い
        naive_result = evaluator.evaluate_rag_pipeline(
            query="What is Paris famous for?",
            retrieved_documents=["Paris info", "London info"],
            retrieved_scores=[0.9, 0.5],
            generated_answer="Paris is located on Earth",  # 事実的だが質問に答えていない
            ground_truth="Paris is famous for its culture and landmarks",
            relevant_documents={"Paris info"},
        )
        
        # シナリオ2: 良いRAG
        good_rag_result = evaluator.evaluate_rag_pipeline(
            query="What is Paris famous for?",
            retrieved_documents=["Paris culture doc", "Paris landmarks doc"],
            retrieved_scores=[0.95, 0.90],
            generated_answer="Paris is famous for its culture and landmarks",
            ground_truth="Paris is famous for its culture and landmarks",
            relevant_documents={"Paris culture doc", "Paris landmarks doc"},
        )
        
        # 良いRAGは検索と生成の両方で高いスコアを持つべき
        assert good_rag_result.end_to_end_score > naive_result.end_to_end_score


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
