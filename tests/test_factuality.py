"""
事実性検証エンジン テストスイート
"""

import pytest
from src.factuality.fact_verifier import (
    FactVerifier, FactClaim, SimpleClaimExtractor, 
    MockEvidenceSearcher, FactCheckStatus, Evidence
)
from src.factuality.confidence_scorer import (
    ConfidenceScorer, SourceCredibilityScorer,
    EvidenceMatchScorer, RecencyScorer
)
from src.factuality.knowledge_base_mapper import (
    KnowledgeBaseMapper, MockKnowledgeBase
)
from src.factuality.hallucination_detector import (
    HallucinationDetector, HallucinationType
)


class TestFactClaim:
    """ファクトクレイムのテスト"""
    
    def test_fact_claim_creation(self):
        """ファクトクレイムの作成"""
        claim = FactClaim(
            text="Paris is the capital of France",
            subject="Paris",
            predicate="is_capital_of",
            object="France",
            confidence=0.9,
        )
        
        assert claim.subject == "Paris"
        assert claim.confidence == 0.9
    
    def test_claim_extraction(self):
        """クレイム抽出"""
        extractor = SimpleClaimExtractor()
        text = "Paris is the capital of France. Tokyo is in Japan."
        
        claims = extractor.extract_claims(text)
        
        assert len(claims) >= 1
        assert claims[0].text.strip() == "Paris is the capital of France"


class TestEvidenceSearch:
    """エビデンス検索のテスト"""
    
    @pytest.mark.asyncio
    async def test_mock_evidence_search(self):
        """モックエビデンス検索"""
        searcher = MockEvidenceSearcher()
        
        claim = FactClaim(
            text="Paris is the capital of France",
            subject="Paris",
            predicate="is_capital_of",
            object="France",
            confidence=0.9,
        )
        
        results = await searcher.search(claim)
        
        assert len(results) > 0
        assert all(isinstance(e, Evidence) for e in results)


class TestConfidenceScorer:
    """信頼度スコアリングのテスト"""
    
    def test_source_credibility_scorer(self):
        """ソース信頼度スコアリング"""
        score = SourceCredibilityScorer.score_source(
            "Wikipedia",
            "https://en.wikipedia.org/wiki/Paris"
        )
        
        assert 0.8 <= score <= 0.95
    
    def test_match_score_calculation(self):
        """一致度スコア計算"""
        claim = "Paris is the capital of France"
        evidence = "Paris is the capital of France"
        
        score = EvidenceMatchScorer.compute_match_score(claim, evidence)
        
        assert score > 0.5  # 高い一致度
    
    def test_contradiction_level(self):
        """矛盾度計算"""
        claim = "Paris is the capital of France"
        evidence = "Paris is not the capital of France"
        
        contradiction = EvidenceMatchScorer.compute_contradiction_level(claim, evidence)
        
        assert contradiction > 0.5  # 矛盾を検出
    
    def test_recency_scoring(self):
        """新鮮度スコアリング"""
        score_recent = RecencyScorer.score_by_date("2026-01-01")
        score_old = RecencyScorer.score_by_date("2010-01-01")
        
        assert score_recent > score_old
    
    def test_confidence_computation(self):
        """総合信頼度計算"""
        scorer = ConfidenceScorer()
        
        evidence_list = [
            {
                "text": "Paris is the capital of France",
                "source": "Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Paris",
                "date": "2025-01-01",
            },
            {
                "text": "Paris, the capital, is in France",
                "source": "Government Official",
                "url": "https://gov.fr/",
                "date": "2024-06-01",
            },
        ]
        
        score, components = scorer.compute_claim_confidence(
            "Paris is the capital of France",
            evidence_list,
        )
        
        assert 0.0 <= score <= 1.0
        assert len(components) > 0
        assert components["source_credibility"].value > 0.7


class TestKnowledgeBaseMapper:
    """知識ベースマッパーのテスト"""
    
    def test_knowledge_base_lookup(self):
        """知識ベースエンティティ検索"""
        kb = MockKnowledgeBase()
        entity = kb.lookup_entity("Paris")
        
        assert entity is not None
        assert entity.name == "Paris"
        assert entity.entity_type == "city"
    
    def test_relationship_lookup(self):
        """関係検索"""
        kb = MockKnowledgeBase()
        relationships = kb.lookup_relationship("Paris", "France", "is_capital_of")
        
        assert len(relationships) > 0
    
    def test_mapper_claim_mapping(self):
        """クレイムマッピング"""
        mapper = KnowledgeBaseMapper()
        
        result = mapper.map_claim_to_knowledge("Paris is the capital of France")
        
        assert "mapped_entities" in result
        assert result["coverage"] > 0
    
    def test_related_facts_retrieval(self):
        """関連事実取得"""
        mapper = KnowledgeBaseMapper()
        facts = mapper.get_related_facts("Paris")
        
        assert len(facts) > 0


class TestHallucinationDetector:
    """Hallucination検出のテスト"""
    
    def test_self_contradiction_detection(self):
        """自己矛盾検出"""
        detector = HallucinationDetector()
        
        text = "Paris is the capital of France. Paris is the capital of Germany."
        report = detector.detect_hallucinations(text)
        
        assert report.hallucination_count > 0
    
    def test_factual_error_detection(self):
        """事実エラー検出"""
        detector = HallucinationDetector()
        
        text = "Paris is the capital of Germany."
        report = detector.detect_hallucinations(text)
        
        assert report.hallucination_count > 0
        factual_errors = [
            i for i in report.hallucination_instances
            if i.type == HallucinationType.FACTUAL
        ]
        assert len(factual_errors) > 0
    
    def test_entity_confusion_detection(self):
        """エンティティ混同検出"""
        detector = HallucinationDetector()
        
        text = "Paris is in Germany."
        report = detector.detect_hallucinations(text)
        
        assert report.hallucination_count > 0
    
    def test_hallucination_rate_calculation(self):
        """Hallucination率計算"""
        detector = HallucinationDetector()
        
        text_clean = "Paris is the capital of France."
        text_hallucinated = "Paris is the capital of Germany. Paris is the capital of Italy."
        
        rate_clean = detector.get_hallucination_rate(text_clean)
        rate_hallucinated = detector.get_hallucination_rate(text_hallucinated)
        
        assert rate_hallucinated > rate_clean
    
    def test_hallucination_correction(self):
        """Hallucination修正"""
        detector = HallucinationDetector()
        
        text = "Paris is the capital of Germany."
        corrected = detector.correct_hallucinations(text)
        
        assert "France" in corrected or corrected != text


class TestFactVerifierIntegration:
    """ファクトチェッカーの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_verify_single_claim(self):
        """単一クレイムの検証"""
        verifier = FactVerifier()
        
        claim = FactClaim(
            text="Paris is the capital of France",
            subject="Paris",
            predicate="is_capital_of",
            object="France",
            confidence=0.9,
        )
        
        result = await verifier.check_claim(claim)
        
        assert result.claim_text == claim.text
        assert result.status in list(FactCheckStatus)
        assert 0.0 <= result.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_verify_text(self):
        """テキスト内のクレイム検証"""
        verifier = FactVerifier()
        
        text = "Paris is the capital of France. Tokyo is in Japan."
        
        results = await verifier.verify_text(text)
        
        assert len(results) > 0
        assert all(hasattr(r, 'claim_text') for r in results)
    
    def test_hallucination_check(self):
        """Hallucination チェック"""
        verifier = FactVerifier()
        
        text = "Paris is the capital of Germany."
        hallucination_report = verifier.check_for_hallucinations(text)
        
        assert "hallucination_count" in hallucination_report
        assert hallucination_report["hallucination_count"] > 0


# 実行用スクリプト
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
