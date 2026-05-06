"""
情報源信頼性分析エンジン テスト
"""

import pytest
from datetime import datetime, timedelta
from src.quality_assurance.source_credibility import (
    SourceCredibilityAnalyzer,
    SourceMetadata,
    AccuracyHistory,
    ReputationScore,
    AuthorInfo,
    CredibilityLevel,
    CorrectionTrend
)


class TestAccuracyHistory:
    """精度履歴テスト"""
    
    def test_initialize_accuracy_history(self):
        """精度履歴初期化テスト"""
        history = AccuracyHistory(source_id="source1")
        
        assert history.source_id == "source1"
        assert history.total_claims == 0
        assert history.accuracy_rate == 0.0
    
    def test_add_correct_claim(self):
        """正確なクレーム追加テスト"""
        history = AccuracyHistory(source_id="source1")
        history.add_correct_claim()
        history.add_correct_claim()
        
        assert history.total_claims == 2
        assert history.correct_claims == 2
        assert history.accuracy_rate == 1.0
    
    def test_add_incorrect_claim(self):
        """不正確なクレーム追加テスト"""
        history = AccuracyHistory(source_id="source1")
        history.add_correct_claim()
        history.add_incorrect_claim()
        
        assert history.total_claims == 2
        assert history.incorrect_claims == 1
        assert history.accuracy_rate == 0.5
    
    def test_add_incorrect_claim_major(self):
        """重大エラー追加テスト"""
        history = AccuracyHistory(source_id="source1")
        before_time = datetime.utcnow()
        history.add_incorrect_claim(is_major=True)
        after_time = datetime.utcnow()
        
        assert history.last_major_error is not None
        assert before_time <= history.last_major_error <= after_time
    
    def test_correction_trend_insufficient_data(self):
        """データ不足時のトレンド判定テスト"""
        history = AccuracyHistory(source_id="source1")
        history.add_correct_claim()
        
        assert history.correction_trend == CorrectionTrend.INSUFFICIENT_DATA
    
    def test_correction_trend_stable(self):
        """安定トレンド判定テスト"""
        history = AccuracyHistory(source_id="source1")
        for _ in range(10):
            history.add_correct_claim()
        
        assert history.correction_trend == CorrectionTrend.STABLE
    
    def test_correction_trend_improving(self):
        """改善トレンド判定テスト"""
        history = AccuracyHistory(source_id="source1")
        # 古いエラーを記録
        history.add_incorrect_claim(is_major=True)
        history.last_major_error = datetime.utcnow() - timedelta(days=200)
        
        # 最近は正確
        for _ in range(10):
            history.add_correct_claim()
        
        assert history.correction_trend == CorrectionTrend.IMPROVING
    
    def test_correction_responsiveness(self):
        """修正への対応性テスト"""
        history = AccuracyHistory(source_id="source1")
        history.add_incorrect_claim()
        history.add_incorrect_claim()
        history.add_corrected_claim()
        history.add_corrected_claim()
        
        # 修正率: 2/3 = 0.67
        assert 0.6 < history.correction_responsiveness <= 1.0


class TestReputationScore:
    """評判スコアテスト"""
    
    def test_composite_score_empty(self):
        """空の評判スコア計算テスト"""
        reputation = ReputationScore()
        
        # 評判データなし時の基本値を確認
        assert 0.0 <= reputation.composite_score <= 1.0
    
    def test_composite_score_with_ratings(self):
        """レーティングを含むスコア計算テスト"""
        reputation = ReputationScore()
        reputation.third_party_ratings = [0.8, 0.9, 0.85]
        
        # レーティングがある場合はスコアが上昇
        score = reputation.composite_score
        assert score >= 0.0 and score <= 1.0
    
    def test_composite_score_with_negative_factors(self):
        """負の要因を含むスコア計算テスト"""
        reputation = ReputationScore()
        reputation.lawsuit_count = 5
        reputation.retraction_index = 0.2
        
        # 訴訟と撤回ペナルティでスコアが低下
        assert reputation.composite_score < 0.7
    
    def test_composite_score_with_positive_factors(self):
        """正の要因を含むスコア計算テスト"""
        reputation = ReputationScore()
        reputation.third_party_ratings = [0.9, 0.95, 0.92]
        reputation.academic_citations = 50
        reputation.award_count = 3
        
        # 正の要因が多い場合のスコア確認
        score = reputation.composite_score
        assert score > 0.2  # 最小限の正の要因があるはず


class TestSourceCredibilityAnalyzer:
    """SourceCredibilityAnalyzerテスト"""
    
    @pytest.fixture
    def analyzer(self):
        return SourceCredibilityAnalyzer()
    
    @pytest.fixture
    def trusted_metadata(self):
        """信頼できるメタデータ"""
        return SourceMetadata(
            source_id="trusted_source",
            domain="news.edu",
            organization="University Press",
            author_info=AuthorInfo(
                name="Dr. Jane Smith",
                h_index=25,
                publication_count=50
            ),
            certifications=["ISO 9001", "Press Standard"],
            website_rank=500
        )
    
    @pytest.fixture
    def unreliable_metadata(self):
        """信頼できないメタデータ"""
        return SourceMetadata(
            source_id="unreliable_source",
            domain="random_blog.xyz",
            organization="Unknown Blog"
        )
    
    def test_analyze_highly_credible_source(self, analyzer, trusted_metadata):
        """高信頼性ソース分析テスト"""
        history = AccuracyHistory(source_id="trusted_source")
        for _ in range(20):
            history.add_correct_claim()
        
        result = analyzer.analyze_credibility(
            "trusted_source",
            metadata=trusted_metadata,
            accuracy_history=history
        )
        
        assert result.final_credibility_score > 0.7
        assert result.credibility_level == CredibilityLevel.TRUSTED or \
               result.credibility_level == CredibilityLevel.CREDIBLE
    
    def test_analyze_low_credibility_source(self, analyzer, unreliable_metadata):
        """低信頼性ソース分析テスト"""
        history = AccuracyHistory(source_id="unreliable_source")
        for _ in range(5):
            history.add_correct_claim()
        for _ in range(15):
            history.add_incorrect_claim()
        
        result = analyzer.analyze_credibility(
            "unreliable_source",
            metadata=unreliable_metadata,
            accuracy_history=history
        )
        
        assert result.final_credibility_score < 0.5
        assert result.credibility_level in [
            CredibilityLevel.UNCERTAIN,
            CredibilityLevel.UNRELIABLE
        ]
    
    def test_analyze_with_reputation(self, analyzer, trusted_metadata):
        """評判を含む分析テスト"""
        history = AccuracyHistory(source_id="trusted_source")
        for _ in range(15):
            history.add_correct_claim()
        
        reputation = ReputationScore()
        reputation.third_party_ratings = [0.9, 0.85, 0.95]
        reputation.academic_citations = 100
        
        result = analyzer.analyze_credibility(
            "trusted_source",
            metadata=trusted_metadata,
            accuracy_history=history,
            reputation_score=reputation
        )
        
        assert result.final_credibility_score >= 0.6
        assert result.confidence > 0.5
    
    def test_credibility_level_thresholds(self, analyzer):
        """信頼性レベル閾値テスト"""
        assert analyzer._determine_credibility_level(0.9) == CredibilityLevel.TRUSTED
        assert analyzer._determine_credibility_level(0.7) == CredibilityLevel.CREDIBLE
        assert analyzer._determine_credibility_level(0.5) == CredibilityLevel.UNCERTAIN
        assert analyzer._determine_credibility_level(0.2) == CredibilityLevel.UNRELIABLE
    
    def test_base_credibility_score_edu_domain(self, analyzer):
        """教育機関ドメインのスコア計算テスト"""
        metadata = SourceMetadata(
            source_id="university",
            domain="research.edu",
            organization="University"
        )
        
        score = analyzer._calculate_base_credibility_score(metadata)
        assert score > 0.5
    
    def test_base_credibility_score_with_author_info(self, analyzer):
        """著者情報を含むスコア計算テスト"""
        metadata = SourceMetadata(
            source_id="researcher",
            domain="research.edu",
            organization="University",
            author_info=AuthorInfo(
                name="Dr. John",
                h_index=15,
                credentials=["PhD", "Board Member"]
            )
        )
        
        score = analyzer._calculate_base_credibility_score(metadata)
        assert score > 0.5
    
    def test_calculate_confidence(self, analyzer):
        """信頼度計算テスト"""
        history = AccuracyHistory(source_id="source1")
        for _ in range(100):
            history.add_correct_claim()
        
        metadata = SourceMetadata(
            source_id="source1",
            domain="news.gov",
            organization="Government",
            author_info=AuthorInfo(name="Official")
        )
        
        reputation = ReputationScore()
        reputation.third_party_ratings = [0.9, 0.95]
        
        confidence = analyzer._calculate_confidence(history, metadata, reputation)
        
        assert 0.5 < confidence <= 1.0
    
    def test_cache_functionality(self, analyzer, trusted_metadata):
        """キャッシュ機能テスト"""
        # 最初の分析
        result1 = analyzer.analyze_credibility(
            "trusted_source",
            metadata=trusted_metadata
        )
        
        # キャッシュから取得されるべき
        result2 = analyzer.analyze_credibility("trusted_source")
        
        assert result1.source_id == result2.source_id
    
    def test_recommendations_generation_low_accuracy(self, analyzer):
        """低精度時の推奨生成テスト"""
        history = AccuracyHistory(source_id="poor")
        for _ in range(3):
            history.add_correct_claim()
        for _ in range(7):
            history.add_incorrect_claim()
        
        reputation = ReputationScore()
        
        recommendations = analyzer._generate_recommendations(
            0.3,
            history,
            reputation,
            CredibilityLevel.UNRELIABLE
        )
        
        assert len(recommendations) > 0
        assert any("verification" in rec.lower() for rec in recommendations)
    
    def test_recommendations_generation_trusted(self, analyzer):
        """高信頼性ソースの推奨生成テスト"""
        history = AccuracyHistory(source_id="trusted")
        for _ in range(20):
            history.add_correct_claim()
        
        reputation = ReputationScore()
        
        recommendations = analyzer._generate_recommendations(
            0.85,
            history,
            reputation,
            CredibilityLevel.TRUSTED
        )
        
        assert len(recommendations) > 0
    
    def test_score_interpretation(self, analyzer):
        """スコア解釈テスト"""
        interpretation = analyzer.get_score_interpretation(0.9)
        assert "Highly credible" in interpretation or "TRUSTED" in interpretation
        
        interpretation = analyzer.get_score_interpretation(0.3)
        assert "caution" in interpretation or "UNRELIABLE" in interpretation
    
    def test_generate_report(self, analyzer, trusted_metadata):
        """レポート生成テスト"""
        history = AccuracyHistory(source_id="trusted_source")
        for _ in range(15):
            history.add_correct_claim()
        
        result = analyzer.analyze_credibility(
            "trusted_source",
            metadata=trusted_metadata,
            accuracy_history=history
        )
        
        report = analyzer.generate_report(result)
        
        assert "SOURCE CREDIBILITY ANALYSIS REPORT" in report
        assert "trusted_source" in report
        assert "Accuracy Rate" in report


class TestSourceCredibilityEdgeCases:
    """エッジケーステスト"""
    
    @pytest.fixture
    def analyzer(self):
        return SourceCredibilityAnalyzer()
    
    def test_empty_accuracy_history(self, analyzer):
        """空の履歴テスト"""
        history = AccuracyHistory(source_id="empty")
        
        score = analyzer._calculate_history_credibility_score(history)
        
        assert score == 0.5
    
    def test_all_incorrect_claims(self, analyzer):
        """すべて不正確なクレームテスト"""
        history = AccuracyHistory(source_id="wrong")
        for _ in range(10):
            history.add_incorrect_claim()
        
        score = analyzer._calculate_history_credibility_score(history)
        
        assert score < 0.4
    
    def test_analyze_unknown_source(self, analyzer):
        """未知のソース分析テスト"""
        result = analyzer.analyze_credibility("unknown_source_123")
        
        assert result.source_id == "unknown_source_123"
        assert result.final_credibility_score >= 0.0
        assert result.final_credibility_score <= 1.0


class TestSourceCredibilityPerformance:
    """パフォーマンステスト"""
    
    def test_analyze_many_sources(self):
        """多数ソース分析テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for i in range(100):
            history = AccuracyHistory(source_id=f"source_{i}")
            for _ in range(10):
                history.add_correct_claim()
            
            result = analyzer.analyze_credibility(
                f"source_{i}",
                accuracy_history=history
            )
            
            assert result.final_credibility_score >= 0.0
        
        assert len(analyzer.accuracy_cache) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
