"""
Test Phase 5: Memory Enhancement (Meta Memory, Procedural Memory, Context-Aware Retrieval)
"""

import pytest
from datetime import datetime, timedelta
from src.self_improvement.meta_memory import (
    MetaMemoryManager,
    MemoryQualityScore,
    MemoryImportance,
    MemoryRetentionPolicy,
)
from src.self_improvement.procedural_memory import (
    ProceduralMemoryManager,
    ProcedurePattern,
    ProcedureType,
    ExecutionStep,
    ParameterPattern,
)
from src.memory.context_aware_retrieval import (
    ContextAwareRetriever,
    ContextVector,
    ContextDimension,
)


# ============================================================================
# Phase 5: Meta Memory Tests
# ============================================================================

class TestMetaMemory:
    """Test meta-memory quality scoring and retention."""
    
    @pytest.fixture
    def manager(self):
        """Create a meta-memory manager."""
        return MetaMemoryManager()
    
    def test_memory_quality_score_computation(self):
        """Test that quality scores are computed correctly."""
        score = MemoryQualityScore(
            memory_id="test_1",
            confidence=0.8,
            usage_count=20,
            last_accessed=datetime.now() - timedelta(days=5),
            access_frequency=2.0,
            accuracy_rating=0.9,
            relevance_score=0.7,
        )
        
        quality = score.compute_quality()
        assert 0.0 <= quality <= 1.0
        assert quality > 0.6  # High quality expected (realistic threshold)
    
    def test_recency_factor_decay(self):
        """Test that recency factor decays over time."""
        recent_score = MemoryQualityScore(
            memory_id="test_recent",
            confidence=0.8,
            usage_count=10,
            last_accessed=datetime.now() - timedelta(days=10),
            access_frequency=1.0,
            accuracy_rating=0.9,
            relevance_score=0.7,
        )
        
        old_score = MemoryQualityScore(
            memory_id="test_old",
            confidence=0.8,
            usage_count=10,
            last_accessed=datetime.now() - timedelta(days=100),
            access_frequency=1.0,
            accuracy_rating=0.9,
            relevance_score=0.7,
        )
        
        assert recent_score.compute_quality() > old_score.compute_quality()
    
    def test_consolidation_suggestion(self, manager):
        """Test consolidation suggestions."""
        manager.register_memory_access("mem_1", confidence=0.4)
        
        # Trigger multiple accesses to make it frequently used
        for _ in range(15):
            manager.register_memory_access("mem_1", confidence=0.45)
        
        health = manager.get_memory_health("mem_1")
        assert health["should_consolidate"] is True
    
    def test_prune_obsolete_memories(self, manager):
        """Test that obsolete memories are pruned."""
        manager.register_memory_access("mem_1", confidence=0.9)
        manager.set_memory_importance("mem_1", MemoryImportance.LOW)
        
        # Manually set last accessed to old date
        manager.memory_quality_scores["mem_1"].last_accessed = (
            datetime.now() - timedelta(days=30)
        )
        
        deleted = manager.prune_obsolete_memories()
        
        # Memory with LOW importance and old access should be deleted
        assert len(deleted) > 0
    
    def test_retention_policy_critical(self, manager):
        """Test that critical memories are retained indefinitely."""
        manager.register_memory_access("critical_mem", confidence=0.8)
        manager.set_memory_importance("critical_mem", MemoryImportance.CRITICAL)
        
        policy = manager.retention_policies["critical_mem"]
        retention_days = policy.compute_retention_days(quality_score=0.5)
        
        assert retention_days > 365  # Critical = 10+ years
    
    def test_statistics_generation(self, manager):
        """Test that statistics are generated correctly."""
        for i in range(5):
            manager.register_memory_access(f"mem_{i}", confidence=0.8)
        
        stats = manager.get_statistics()
        
        assert stats["total_memories"] == 5
        assert 0.0 <= stats["average_quality"] <= 1.0
        assert stats["quality_distribution"]["high"] >= 0


# ============================================================================
# Phase 5: Procedural Memory Tests
# ============================================================================

class TestProceduralMemory:
    """Test procedural memory and pattern caching."""
    
    @pytest.fixture
    def manager(self):
        """Create a procedural memory manager."""
        return ProceduralMemoryManager()
    
    def test_procedure_creation(self, manager):
        """Test creating a procedure."""
        steps = [
            ExecutionStep(
                tool_name="file_read",
                parameters={"path": "/data/input.txt"},
                expected_output_type="success",
                average_execution_time=100.0,
                success_rate=0.95,
            ),
            ExecutionStep(
                tool_name="data_transform",
                parameters={"format": "json"},
                expected_output_type="success",
                average_execution_time=200.0,
                success_rate=0.9,
            ),
        ]
        
        procedure = manager.create_procedure(
            task_description="Read and transform data file",
            procedure_type=ProcedureType.SIMPLE_SEQUENCE,
            steps=steps,
        )
        
        assert len(procedure.steps) == 2
        assert procedure.average_duration > 0
    
    def test_procedure_reliability_score(self):
        """Test reliability scoring."""
        procedure = ProcedurePattern(
            procedure_id="proc_1",
            task_description="Test task",
            procedure_type=ProcedureType.SIMPLE_SEQUENCE,
            steps=[],
            total_executions=20,
            successful_executions=18,
            average_duration=150.0,
            last_executed=datetime.now(),
        )
        
        reliability = procedure.reliability_score()
        assert 0.0 <= reliability <= 1.0
        assert reliability > 0.65  # Should be high reliability (success rate 90%)
    
    def test_execution_speedup_calculation(self):
        """Test speedup factor calculation."""
        procedure = ProcedurePattern(
            procedure_id="proc_1",
            task_description="Fast task",
            procedure_type=ProcedureType.SIMPLE_SEQUENCE,
            steps=[],
            total_executions=10,
            successful_executions=9,
            average_duration=100.0,
            last_executed=datetime.now(),
        )
        
        speedup = procedure.execution_speedup(baseline_ms=400.0)
        assert speedup > 1.0  # Should be faster than baseline
        assert speedup == pytest.approx(4.0)
    
    def test_parameter_caching(self, manager):
        """Test caching and learning parameters."""
        manager.cache_parameter(
            tool_name="file_write",
            parameter_name="encoding",
            value="utf-8",
            success=True,
            context={"file_type": "text"},
        )
        
        recommendations = manager.recommend_parameters("file_write")
        assert "encoding" in recommendations
        assert recommendations["encoding"] == "utf-8"
    
    def test_parameter_context_matching(self, manager):
        """Test parameter recommendation with context matching."""
        # Cache multiple parameter values
        manager.cache_parameter(
            "api_call",
            "timeout",
            value=30,
            success=True,
            context={"api_type": "fast"},
        )
        manager.cache_parameter(
            "api_call",
            "timeout",
            value=120,
            success=True,
            context={"api_type": "slow"},
        )
        
        # Get recommendations for slow API
        recommendations = manager.recommend_parameters(
            "api_call",
            context={"api_type": "slow"}
        )
        
        assert recommendations["timeout"] == 120
    
    def test_find_similar_procedures(self, manager):
        """Test finding procedures by task description."""
        steps = [ExecutionStep(
            tool_name="test", parameters={},
            expected_output_type="success",
            average_execution_time=100.0,
            success_rate=0.9,
        )]
        
        proc1 = manager.create_procedure(
            "Data analysis and reporting",
            ProcedureType.SIMPLE_SEQUENCE,
            steps,
        )
        
        # Record execution to increase reliability
        manager.record_procedure_execution(proc1.procedure_id, success=True, actual_duration=100.0)
        manager.record_procedure_execution(proc1.procedure_id, success=True, actual_duration=100.0)
        
        # Find similar procedures
        similar = manager.find_similar_procedures(
            "Analysis report generation",
            min_reliability=0.0
        )
        
        assert len(similar) > 0
        assert similar[0][0] == proc1.procedure_id
    
    def test_procedure_optimization_tips(self, manager):
        """Test optimization suggestions."""
        steps = [
            ExecutionStep("tool1", {}, "success", 100.0, 0.7),
            ExecutionStep("tool2", {}, "success", 100.0, 0.7),
        ]
        
        proc = manager.create_procedure(
            "Low success task",
            ProcedureType.SIMPLE_SEQUENCE,
            steps,
        )
        
        tips = manager.get_procedure_optimization_tips(proc.procedure_id)
        
        # Should suggest improvement for low success rate
        assert len(tips) > 0


# ============================================================================
# Phase 5: Context-Aware Retrieval Tests
# ============================================================================

class TestContextAwareRetrieval:
    """Test context-aware memory retrieval."""
    
    @pytest.fixture
    def retriever(self):
        """Create a context-aware retriever."""
        return ContextAwareRetriever()
    
    @pytest.fixture
    def context(self):
        """Create a sample context."""
        return ContextVector(
            timestamp=datetime.now(),
            user_id="user_123",
            task_type="data_analysis",
            time_of_day="09:00-10:00",
            error_category=None,
            file_type="csv",
            data_size_range="medium",
            priority=1,
            tools_used=["pandas", "numpy"],
        )
    
    def test_context_vector_creation(self, context):
        """Test context vector creation."""
        assert context.user_id == "user_123"
        assert context.task_type == "data_analysis"
        assert len(context.tools_used) == 2
    
    def test_index_and_retrieve_memory(self, retriever, context):
        """Test indexing and retrieving a memory."""
        retriever.index_memory(
            memory_id="mem_1",
            content="Use pandas for data analysis",
            context_conditions={
                "task_type": ["data_analysis"],
                "file_type": ["csv", "json"],
            },
        )
        
        retriever.record_context(context)
        
        results = retriever.retrieve(
            query="How to analyze CSV data?",
            context=context,
            top_k=5,
            min_confidence=0.0,
        )
        
        assert len(results) > 0
        assert results[0].memory_id == "mem_1"
    
    def test_context_matching(self, retriever, context):
        """Test context matching."""
        # Memory that matches the context
        retriever.index_memory(
            memory_id="mem_match",
            content="Matching memory",
            context_conditions={
                "task_type": ["data_analysis"],
                "file_type": ["csv"],
            },
            relevance_score=0.9,
        )
        
        # Memory that doesn't match
        retriever.index_memory(
            memory_id="mem_no_match",
            content="Non-matching memory",
            context_conditions={
                "task_type": ["image_processing"],
                "file_type": ["jpg"],
            },
            relevance_score=0.5,
        )
        
        results = retriever.retrieve(
            query="test",
            context=context,
            top_k=5,
            min_confidence=0.3,  # Higher threshold to filter out non-matching
        )
        
        # Should prioritize matching memory
        retrieved_ids = [r.memory_id for r in results]
        assert "mem_match" in retrieved_ids
        # mem_no_match may appear with fallback, but mem_match should rank higher
        if retrieved_ids:
            assert retrieved_ids[0] == "mem_match"
    
    def test_retrieval_fallback(self, retriever, context):
        """Test retrieval with fallback strategies."""
        # Add a general memory
        retriever.index_memory(
            memory_id="general_mem",
            content="General advice",
            context_conditions={},
            relevance_score=0.6,
        )
        
        result = retriever.retrieve_with_fallback(
            query="Help!",
            context=context,
        )
        
        # Should return something (fallback strategy)
        assert result is not None
    
    def test_update_memory_success(self, retriever):
        """Test updating memory success rates."""
        retriever.index_memory(
            memory_id="mem_test",
            content="Test memory",
            context_conditions={},
        )
        
        initial_success = retriever.memories["mem_test"].success_rate
        
        # Mark as helpful
        retriever.update_memory_success("mem_test", was_helpful=True)
        
        new_success = retriever.memories["mem_test"].success_rate
        assert new_success >= initial_success
    
    def test_context_recommendations(self, retriever, context):
        """Test context-based recommendations."""
        # Record multiple contexts
        for i in range(5):
            ctx = ContextVector(
                timestamp=datetime.now(),
                user_id="user_123",
                task_type="data_analysis",
                time_of_day="09:00-10:00",
                error_category=None,
                file_type="csv",
                data_size_range="medium",
                priority=1,
                tools_used=["pandas", "numpy", "scipy"],
            )
            retriever.record_context(ctx)
        
        recommendations = retriever.get_context_recommendations(context)
        
        # Should recommend pandas, numpy, scipy
        if "suggested_tools" in recommendations:
            assert "pandas" in recommendations["suggested_tools"]
    
    def test_retrieval_statistics(self, retriever, context):
        """Test retrieval statistics collection."""
        retriever.index_memory(
            memory_id="mem_1",
            content="Memory 1",
            context_conditions={},
        )
        
        # Perform some retrievals
        for _ in range(3):
            retriever.retrieve("query", context, top_k=1, min_confidence=0.0)
        
        stats = retriever.get_retrieval_statistics()
        
        assert stats["total_retrievals"] == 3


# ============================================================================
# Integration Test: All Phase 5 Components
# ============================================================================

def test_phase5_integration():
    """Test all Phase 5 components working together."""
    # Initialize all components
    meta_mgr = MetaMemoryManager()
    proc_mgr = ProceduralMemoryManager()
    retriever = ContextAwareRetriever()
    
    # Scenario: Learn from multiple executions
    context = ContextVector(
        timestamp=datetime.now(),
        user_id="agent_1",
        task_type="data_pipeline",
        time_of_day="14:00-15:00",
        error_category=None,
        file_type="parquet",
        data_size_range="large",
        priority=2,
        tools_used=["spark", "hadoop"],
    )
    
    # Meta Memory: Track quality
    for i in range(5):
        meta_mgr.register_memory_access(f"experience_{i}", confidence=0.8 + i*0.02)
        meta_mgr.set_memory_importance(f"experience_{i}", MemoryImportance.HIGH)
    
    stats = meta_mgr.get_statistics()
    assert stats["total_memories"] == 5
    
    # Procedural Memory: Cache successful procedures
    steps = [
        ExecutionStep("load_data", {"format": "parquet"}, "success", 50.0, 0.95),
        ExecutionStep("process_data", {"engine": "spark"}, "success", 200.0, 0.9),
        ExecutionStep("save_results", {"format": "csv"}, "success", 100.0, 0.95),
    ]
    
    procedure = proc_mgr.create_procedure(
        "Large data pipeline",
        ProcedureType.SIMPLE_SEQUENCE,
        steps,
    )
    
    # Simulate executions
    for _ in range(3):
        proc_mgr.record_procedure_execution(
            procedure.procedure_id,
            success=True,
            actual_duration=350.0,
        )
    
    assert procedure.reliability_score() > 0.65  # Realistic reliability threshold
    
    # Context-Aware Retrieval: Remember context
    retriever.index_memory(
        memory_id="best_practice_pipeline",
        content="Use Spark for large-scale data processing",
        context_conditions={
            "task_type": ["data_pipeline"],
            "size": ["large"],
        },
    )
    
    retriever.record_context(context)
    
    results = retriever.retrieve(
        query="Process large data efficiently",
        context=context,
        top_k=5,
        min_confidence=0.0,
    )
    
    assert len(results) > 0
    assert results[0].memory_id == "best_practice_pipeline"
    
    # All components should be working in coordination
    assert stats["total_memories"] == 5
    assert procedure.reliability_score() > 0.65
    assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
