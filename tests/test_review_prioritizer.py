"""
レビュー優先度判定エンジン テスト
"""

import pytest
from datetime import datetime, timedelta
from src.quality_assurance.review_prioritizer import (
    ReviewPrioritizer,
    ReviewItem,
    PriorityLevel,
    UrgencyLevel
)


class TestReviewPrioritizer:
    """ReviewPrioritizerテスト"""
    
    @pytest.fixture
    def prioritizer(self):
        return ReviewPrioritizer()
    
    @pytest.fixture
    def sample_item(self):
        """サンプルレビュー項目"""
        return ReviewItem(
            item_id="test_item_1",
            item_type="source",
            content="Sample review content",
            required_expertise=["journalism", "verification"],
            deadline=datetime.utcnow() + timedelta(hours=24),
            priority_keywords=[]
        )
    
    def test_calculate_priority_urgent(self, prioritizer):
        """緊急アイテムの優先度計算テスト"""
        item = ReviewItem(
            item_id="urgent_item",
            item_type="viral",
            content="Breaking news" * 100,
            required_expertise=["news"],
            deadline=datetime.utcnow() + timedelta(hours=12),
            priority_keywords=["breaking", "urgent"]
        )
        
        priority = prioritizer.calculate_priority(item)
        
        assert priority.priority_level == PriorityLevel.CRITICAL or \
               priority.priority_level == PriorityLevel.HIGH
        assert priority.urgency_level == UrgencyLevel.IMMEDIATE
    
    def test_calculate_priority_normal(self, prioritizer, sample_item):
        """通常アイテムの優先度計算テスト"""
        priority = prioritizer.calculate_priority(sample_item)
        
        assert 0.0 <= priority.final_priority_score <= 1.0
        assert priority.priority_level in PriorityLevel
    
    def test_urgency_level_determination(self, prioritizer):
        """緊急度レベル判定テスト"""
        # 期限なし
        item1 = ReviewItem(
            item_id="item1",
            item_type="source",
            content="test",
            required_expertise=[],
            deadline=None
        )
        priority1 = prioritizer.calculate_priority(item1)
        assert priority1.urgency_level == UrgencyLevel.FLEXIBLE
        
        # 24時間以内
        item2 = ReviewItem(
            item_id="item2",
            item_type="source",
            content="test",
            required_expertise=[],
            deadline=datetime.utcnow() + timedelta(hours=12)
        )
        priority2 = prioritizer.calculate_priority(item2)
        assert priority2.urgency_level == UrgencyLevel.IMMEDIATE
    
    def test_priority_level_determination(self, prioritizer):
        """優先度レベル判定テスト"""
        # 重大度の高いアイテム
        critical_item = ReviewItem(
            item_id="critical",
            item_type="viral",
            content="dangerous misinformation" * 100,
            required_expertise=["expert1", "expert2", "expert3"],
            deadline=datetime.utcnow() + timedelta(hours=6),
            priority_keywords=["dangerous", "viral"]
        )
        
        priority = prioritizer.calculate_priority(critical_item)
        
        assert priority.priority_level in [PriorityLevel.CRITICAL, PriorityLevel.HIGH]
    
    def test_find_best_match(self, prioritizer):
        """最適な専門家マッチングテスト"""
        # モック専門家を作成
        class MockExpert:
            def __init__(self, expert_id, expertise_areas, active_reviews=0):
                self.expert_id = expert_id
                self.expertise_areas = expertise_areas
                self.expertise_levels = {area: type('obj', (object,), {'value': 'senior'}) 
                                        for area in expertise_areas}
                self.current_active_reviews = active_reviews
                self.max_concurrent_reviews = 5
        
        experts = [
            MockExpert("exp1", ["journalism", "verification"]),
            MockExpert("exp2", ["tech", "security"]),
            MockExpert("exp3", ["journalism"], active_reviews=5)  # 無くて
        ]
        
        item = ReviewItem(
            item_id="test",
            item_type="source",
            content="test",
            required_expertise=["journalism"]
        )
        
        performance = {}
        match = prioritizer.find_best_match(item, experts, performance)
        
        assert match is not None
        assert match.expert_id in ["exp1", "exp2"]
    
    def test_rank_candidates(self, prioritizer):
        """候補者順位付けテスト"""
        class MockExpert:
            def __init__(self, expert_id, expertise_areas, active_reviews=0):
                self.expert_id = expert_id
                self.expertise_areas = expertise_areas
                self.expertise_levels = {area: type('obj', (object,), {'value': 'senior'}) 
                                        for area in expertise_areas}
                self.current_active_reviews = active_reviews
                self.max_concurrent_reviews = 5
        
        experts = [
            MockExpert("exp1", ["journalism", "verification"]),
            MockExpert("exp2", ["journalism"]),
            MockExpert("exp3", ["verification"])
        ]
        
        item = ReviewItem(
            item_id="test",
            item_type="source",
            content="test",
            required_expertise=["journalism", "verification"]
        )
        
        performance = {}
        rankings = prioritizer.rank_candidates(item, experts, performance)
        
        assert len(rankings) > 0
        # スコアが降順になっているはず
        for i in range(len(rankings) - 1):
            assert rankings[i].final_match_score >= rankings[i+1].final_match_score
    
    def test_generate_assignment_report(self, prioritizer, sample_item):
        """割当レポート生成テスト"""
        priority = prioritizer.calculate_priority(sample_item)
        
        report = prioritizer.generate_assignment_report(priority, [])
        
        assert "REVIEW ASSIGNMENT REPORT" in report
        assert "Priority Level" in report
        assert priority.item_id in report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
