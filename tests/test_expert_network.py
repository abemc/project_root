"""
専門家ネットワーク管理システム テスト
"""

import pytest
from datetime import datetime, timedelta
from src.quality_assurance.expert_network import (
    ExpertNetworkManager,
    ExpertLevel,
    AvailabilityStatus
)


class TestExpertNetworkManager:
    """ExpertNetworkManagerテスト"""
    
    @pytest.fixture
    def manager(self):
        return ExpertNetworkManager()
    
    def test_register_expert(self, manager):
        """専門家登録テスト"""
        profile = manager.register_expert(
            name="Dr. Jane Smith",
            email="jane@university.edu",
            expertise_areas=["medicine", "healthcare"],
            affiliation="University Hospital"
        )
        
        assert profile.name == "Dr. Jane Smith"
        assert profile.email == "jane@university.edu"
        assert "medicine" in profile.expertise_areas
        assert len(profile.expertise_levels) == 2
    
    def test_get_expert(self, manager):
        """専門家取得テスト"""
        profile = manager.register_expert(
            name="Dr. John Doe",
            email="john@university.edu",
            expertise_areas=["physics"]
        )
        
        retrieved = manager.get_expert(profile.expert_id)
        
        assert retrieved is not None
        assert retrieved.name == "Dr. John Doe"
    
    def test_update_expertise_level(self, manager):
        """専門領域レベル更新テスト"""
        profile = manager.register_expert(
            name="Dr. Test",
            email="test@test.edu",
            expertise_areas=["AI"]
        )
        
        result = manager.update_expertise_level(
            profile.expert_id,
            "AI",
            ExpertLevel.SENIOR
        )
        
        assert result is True
        updated = manager.get_expert(profile.expert_id)
        assert updated.expertise_levels["AI"] == ExpertLevel.SENIOR
    
    def test_get_experts_by_expertise(self, manager):
        """専門領域別専門家取得テスト"""
        manager.register_expert(
            name="Expert 1",
            email="exp1@test.edu",
            expertise_areas=["AI", "ML"]
        )
        manager.register_expert(
            name="Expert 2",
            email="exp2@test.edu",
            expertise_areas=["ML", "Data"]
        )
        
        ai_experts = manager.get_experts_by_expertise("AI")
        
        assert len(ai_experts) == 1
        assert ai_experts[0].name == "Expert 1"
    
    def test_set_availability(self, manager):
        """可用性設定テスト"""
        profile = manager.register_expert(
            name="Dr. Available",
            email="avail@test.edu",
            expertise_areas=["tech"]
        )
        
        result = manager.set_availability(
            profile.expert_id,
            AvailabilityStatus.BUSY
        )
        
        assert result is True
        updated = manager.get_expert(profile.expert_id)
        assert updated.availability_status == AvailabilityStatus.BUSY
    
    def test_get_available_experts(self, manager):
        """利用可能専門家取得テスト"""
        expert1 = manager.register_expert(
            name="Available",
            email="avail@test.edu",
            expertise_areas=["tech"]
        )
        expert2 = manager.register_expert(
            name="Busy",
            email="busy@test.edu",
            expertise_areas=["tech"]
        )
        
        manager.set_availability(expert2.expert_id, AvailabilityStatus.BUSY)
        
        available = manager.get_available_experts()
        
        assert len(available) == 1
        assert available[0].expert_id == expert1.expert_id
    
    def test_assign_review(self, manager):
        """レビュー割当テスト"""
        profile = manager.register_expert(
            name="Reviewer",
            email="reviewer@test.edu",
            expertise_areas=["review"]
        )
        
        assignment = manager.assign_review(
            profile.expert_id,
            "item_123",
            "source"
        )
        
        assert assignment is not None
        assert assignment.expert_id == profile.expert_id
        assert assignment.status == "pending"
    
    def test_complete_review(self, manager):
        """レビュー完了テスト"""
        profile = manager.register_expert(
            name="Reviewer",
            email="reviewer@test.edu",
            expertise_areas=["review"]
        )
        
        assignment = manager.assign_review(
            profile.expert_id,
            "item_123",
            "source"
        )
        
        result = manager.complete_review(
            assignment.assignment_id,
            "Looks good",
            approved=True
        )
        
        assert result is True
        perf = manager.get_performance(profile.expert_id)
        assert perf.completed_reviews == 1
    
    def test_update_performance(self, manager):
        """パフォーマンス更新テスト"""
        profile = manager.register_expert(
            name="Expert",
            email="expert@test.edu",
            expertise_areas=["test"]
        )
        
        manager.update_expert_performance(
            profile.expert_id,
            accuracy=0.95,
            reliability=0.88,
            feedback=0.92
        )
        
        perf = manager.get_performance(profile.expert_id)
        
        assert perf.accuracy_score == 0.95
        assert perf.reliability_score == 0.88
        assert perf.feedback_score == 0.92
    
    def test_get_statistics(self, manager):
        """統計情報取得テスト"""
        for i in range(3):
            manager.register_expert(
                name=f"Expert {i}",
                email=f"expert{i}@test.edu",
                expertise_areas=["tech"]
            )
        
        stats = manager.get_expert_statistics()
        
        assert stats["total_experts"] == 3
        assert stats["expertise_areas"] == 1
    
    def test_get_top_performers(self, manager):
        """トップパフォーマー取得テスト"""
        experts = []
        for i in range(5):
            p = manager.register_expert(
                name=f"Expert {i}",
                email=f"expert{i}@test.edu",
                expertise_areas=["tech"]
            )
            experts.append(p)
        
        # パフォーマンスを設定
        for i, expert in enumerate(experts):
            manager.update_expert_performance(
                expert.expert_id,
                accuracy=0.5 + (i * 0.1),
                reliability=0.5 + (i * 0.1)
            )
        
        top = manager.get_top_performers(3)
        
        assert len(top) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
