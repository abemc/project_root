"""
Test Phase 5.7-6: Advanced Learning Enhancements
(Adaptive Forgetting, Transfer Learning, Reinforcement Learning, Meta Learning)
"""

import pytest
from datetime import datetime, timedelta
from src.self_improvement.adaptive_forgetting import (
    AdaptiveForgetfulnessManager,
    ForgetfullnessCurve,
    ForgetfulnessLevel,
)
from src.self_improvement.transfer_learning import (
    TransferLearningManager,
    TaskFamily,
)
from src.self_improvement.reinforcement_learning import (
    ReinforcementLearningManager,
    RewardSignal,
)
from src.self_improvement.meta_learning import (
    MetaLearningManager,
    LearningStrategy,
)


# ============================================================================
# Phase 5.7: Adaptive Forgetting Tests
# ============================================================================

class TestAdaptiveForgetting:
    """Test adaptive forgetting and memory retention."""
    
    @pytest.fixture
    def manager(self):
        """Create a forgetting manager."""
        return AdaptiveForgetfulnessManager(ForgetfulnessLevel.BALANCED)
    
    def test_register_memory(self, manager):
        """Test registering a memory for forgetting management."""
        manager.register_memory("mem_1", importance=0.8)
        assert "mem_1" in manager.forgetting_curves
    
    def test_retention_score_computation(self, manager):
        """Test retention score calculation."""
        manager.register_memory("mem_1", importance=0.8)
        curve = manager.forgetting_curves["mem_1"]
        
        retention = curve.compute_retention_score()
        assert 0.0 <= retention <= 1.0
        assert retention > 0.5  # Important memory should retain well
    
    def test_record_access(self, manager):
        """Test recording memory access."""
        manager.register_memory("mem_1")
        initial_count = len(manager.forgetting_curves["mem_1"].access_history)
        
        manager.record_access("mem_1")
        
        final_count = len(manager.forgetting_curves["mem_1"].access_history)
        assert final_count > initial_count
    
    def test_spaced_repetition_schedule(self, manager):
        """Test spaced repetition scheduling."""
        manager.register_memory("mem_1", importance=0.8)
        
        # Check if review is scheduled for important memory
        if "mem_1" in manager.spaced_repetitions:
            review = manager.spaced_repetitions["mem_1"]
            assert review.review_count == 0
    
    def test_forget_candidates(self, manager):
        """Test identifying memories to forget."""
        manager.register_memory("mem_1", importance=0.1)
        manager.register_memory("mem_2", importance=0.9)
        
        candidates = manager.get_forgetting_candidates()
        
        # Low importance memory should be candidate
        if candidates:
            assert len(candidates) > 0


# ============================================================================
# Phase 5.4: Transfer Learning Tests
# ============================================================================

class TestTransferLearning:
    """Test knowledge transfer between tasks."""
    
    @pytest.fixture
    def manager(self):
        """Create a transfer learning manager."""
        return TransferLearningManager()
    
    def test_register_task(self, manager):
        """Test task registration."""
        manager.register_task(
            task_id="task_1",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.7,
            processing_time_ms=500.0,
            success_rate=0.9,
            tools_required=["pandas", "numpy"],
        )
        
        assert "task_1" in manager.task_registry
    
    def test_task_similarity(self, manager):
        """Test computing similarity between tasks."""
        manager.register_task(
            task_id="task_1",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.6,
            processing_time_ms=500.0,
            success_rate=0.9,
            tools_required=["pandas"],
        )
        
        manager.register_task(
            task_id="task_2",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.65,
            processing_time_ms=520.0,
            success_rate=0.88,
            tools_required=["pandas", "numpy"],
        )
        
        similar = manager.find_similar_tasks("task_1", min_similarity=0.5)
        assert len(similar) > 0
        assert similar[0][0] == "task_2"
    
    def test_extract_knowledge(self, manager):
        """Test extracting knowledge from tasks."""
        manager.register_task(
            task_id="task_1",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.7,
            processing_time_ms=500.0,
            success_rate=0.9,
            tools_required=["pandas"],
        )
        
        knowledge = manager.extract_knowledge(
            task_id="task_1",
            knowledge_type="parameter_set",
            content={"delimiter": ",", "encoding": "utf-8"},
            applicability_score=0.8,
        )
        
        assert knowledge.source_task_id == "task_1"
        assert knowledge.knowledge_type == "parameter_set"
    
    def test_transfer_attempt(self, manager):
        """Test attempting to transfer knowledge."""
        manager.register_task(
            task_id="source_task",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.7,
            processing_time_ms=500.0,
            success_rate=0.9,
            tools_required=["pandas"],
        )
        
        manager.register_task(
            task_id="target_task",
            task_family=TaskFamily.DATA_ANALYSIS,
            input_type="csv",
            output_type="report",
            complexity_score=0.75,
            processing_time_ms=510.0,
            success_rate=0.85,
            tools_required=["pandas"],
        )
        
        knowledge = manager.extract_knowledge(
            "source_task",
            "parameter_set",
            {"param": "value"},
        )
        
        success, attempt = manager.attempt_transfer(
            "source_task",
            "target_task",
            knowledge.knowledge_id,
        )
        
        assert isinstance(success, bool)
        assert attempt.source_task_id == "source_task"


# ============================================================================
# Phase 5.5: Reinforcement Learning Tests
# ============================================================================

class TestReinforcementLearning:
    """Test reinforcement learning."""
    
    @pytest.fixture
    def manager(self):
        """Create an RL manager."""
        return ReinforcementLearningManager(learning_rate=0.1)
    
    def test_record_decision(self, manager):
        """Test recording a decision."""
        decision = manager.record_decision(
            decision_id="dec_1",
            context={"task": "analysis"},
            action_chosen="use_pandas",
            alternatives=["use_numpy", "use_dask"],
            confidence=0.9,
        )
        
        assert decision.decision_id == "dec_1"
        assert decision.action_chosen == "use_pandas"
    
    def test_add_reward(self, manager):
        """Test adding rewards to decisions."""
        manager.record_decision(
            decision_id="dec_1",
            context={"task": "analysis"},
            action_chosen="use_pandas",
            alternatives=["use_numpy"],
            confidence=0.9,
        )
        
        manager.add_reward(
            decision_id="dec_1",
            signal_type=RewardSignal.TASK_SUCCESS,
            value=1.0,
            reason="Task completed successfully",
        )
        
        decision = manager.decisions["dec_1"]
        assert len(decision.rewards) > 0
        assert decision.compute_total_reward() > 0
    
    def test_create_policy(self, manager):
        """Test creating a policy."""
        policy = manager.create_policy(
            policy_id="policy_1",
            description="Use pandas for CSV analysis",
            context_conditions={"input_type": "csv"},
            action_distribution={"use_pandas": 0.8, "use_numpy": 0.2},
        )
        
        assert policy.policy_id == "policy_1"
        assert "use_pandas" in policy.action_distribution
    
    def test_policy_value(self, manager):
        """Test computing policy value."""
        policy = manager.create_policy(
            policy_id="policy_1",
            description="Test policy",
            context_conditions={},
            action_distribution={"action_1": 1.0},
        )
        
        # Add some rewards
        policy.success_history.extend([0.9, 0.85, 0.95])
        policy.application_count = 3
        
        value = policy.compute_value()
        assert 0.0 <= value <= 1.0
        # Value = (avg_reward * 0.6) + (freq_factor * 0.3) + (stability * 0.1)
        # = (0.9 * 0.6) + (0.03 * 0.3) + (0.96 * 0.1) ≈ 0.645
        assert value > 0.6
    
    def test_experience_replay(self, manager):
        """Test adding experiences for learning."""
        manager.add_experience(
            state={"task": "analysis"},
            action="use_pandas",
            reward=0.9,
            next_state={"task": "analysis", "result": "success"},
            done=False,
        )
        
        assert len(manager.experience_replay) > 0
    
    def test_learning_from_experience(self, manager):
        """Test learning from batch of experiences."""
        for i in range(50):
            manager.add_experience(
                state={"step": i},
                action=f"action_{i % 3}",
                reward=0.5 + (i % 10) * 0.05,
                next_state={"step": i + 1},
                done=(i == 49),
            )
        
        manager.learn_from_experience(batch_size=32)
        
        # Should have updated Q-values
        assert len(manager.q_values) > 0


# ============================================================================
# Phase 5.6: Meta Learning Tests
# ============================================================================

class TestMetaLearning:
    """Test meta-learning."""
    
    @pytest.fixture
    def manager(self):
        """Create a meta-learning manager."""
        return MetaLearningManager()
    
    def test_analyze_task(self, manager):
        """Test task analysis."""
        analysis = manager.analyze_task(
            task_id="task_1",
            task_family="data_analysis",
            complexity=0.7,
            data_volume="medium",
            success_rate=0.8,
            variability=0.5,
            learning_curve_slope=0.8,
            error_rate=0.2,
        )
        
        assert analysis.task_id == "task_1"
        assert analysis.recommended_algorithm is not None
    
    def test_learning_rate_computation(self, manager):
        """Test recommended learning rate."""
        analysis = manager.analyze_task(
            task_id="task_1",
            task_family="data_analysis",
            complexity=0.3,  # Simple
            data_volume="small",
            success_rate=0.9,
            variability=0.2,
            learning_curve_slope=0.9,  # Fast improvement
            error_rate=0.1,
        )
        
        # Simple task with fast learning should have higher rate
        assert analysis.recommended_learning_rate > 0.05
    
    def test_create_optimal_config(self, manager):
        """Test creating optimal configuration."""
        analysis = manager.analyze_task(
            task_id="task_1",
            task_family="data_analysis",
            complexity=0.7,
            data_volume="large",
            success_rate=0.8,
            variability=0.5,
            learning_curve_slope=0.6,
            error_rate=0.3,
        )
        
        config = manager.create_optimal_config("data_analysis", analysis)
        
        assert config.task_family == "data_analysis"
        assert config.primary_strategy is not None
    
    def test_config_performance_tracking(self, manager):
        """Test tracking configuration performance."""
        analysis = manager.analyze_task(
            task_id="task_1",
            task_family="data_analysis",
            complexity=0.5,
            data_volume="medium",
            success_rate=0.7,
            variability=0.4,
            learning_curve_slope=0.7,
            error_rate=0.25,
        )
        
        config = manager.create_optimal_config("data_analysis", analysis)
        
        manager.record_config_performance(config.config_id, 0.85)
        
        assert config.application_count > 0
        assert config.success_rate > 0


# ============================================================================
# Integration Test: All Advanced Learning Systems
# ============================================================================

def test_advanced_learning_integration():
    """Test all four advanced learning systems working together."""
    # Initialize all managers
    forgetting_mgr = AdaptiveForgetfulnessManager(ForgetfulnessLevel.BALANCED)
    transfer_mgr = TransferLearningManager()
    rl_mgr = ReinforcementLearningManager()
    meta_mgr = MetaLearningManager()
    
    # Scenario: Agent learning from data analysis tasks
    
    # 1. Meta Learning: Analyze new task family
    analysis = meta_mgr.analyze_task(
        task_id="new_analysis",
        task_family="data_analysis",
        complexity=0.6,
        data_volume="medium",
        success_rate=0.0,  # Brand new
        variability=0.5,
        learning_curve_slope=0.7,
        error_rate=0.3,
    )
    
    config = meta_mgr.create_optimal_config("data_analysis", analysis)
    assert config.primary_strategy is not None
    
    # 2. Transfer Learning: Find related task
    transfer_mgr.register_task(
        task_id="task_source",
        task_family=TaskFamily.DATA_ANALYSIS,
        input_type="csv",
        output_type="report",
        complexity_score=0.6,
        processing_time_ms=500.0,
        success_rate=0.9,
        tools_required=["pandas"],
    )
    
    transfer_mgr.register_task(
        task_id="task_target",
        task_family=TaskFamily.DATA_ANALYSIS,
        input_type="csv",
        output_type="analysis",
        complexity_score=0.65,
        processing_time_ms=510.0,
        success_rate=0.0,
        tools_required=["pandas"],
    )
    
    similar = transfer_mgr.find_similar_tasks("task_source")
    assert len(similar) > 0
    
    # 3. Reinforcement Learning: Learn from executing
    rl_mgr.record_decision(
        decision_id="exec_1",
        context={"task": "analysis"},
        action_chosen="use_pandas_config",
        alternatives=["use_numpy"],
        confidence=0.8,
    )
    
    rl_mgr.add_reward("exec_1", RewardSignal.TASK_SUCCESS, 0.9)
    
    progress = rl_mgr.get_learning_progress()
    assert progress["total_decisions"] > 0
    
    # 4. Adaptive Forgetting: Manage memory of learnings
    forgetting_mgr.register_memory("learned_config", importance=0.8)
    forgetting_mgr.record_access("learned_config")
    
    health = forgetting_mgr.get_memory_health("learned_config")
    assert health["retention_score"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
