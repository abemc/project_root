"""
Phase 5 Integration Layer for RAG Agent

This module provides unified access to all Phase 5 learning and memory systems,
integrating them seamlessly with the RAGAgent workflow.

Key Components:
- Memory Management: Meta Memory, Procedural Memory, Context-Aware Retrieval
- Learning Systems: Transfer Learning, Reinforcement Learning
- Optimization: Meta Learning, Adaptive Forgetting
"""

from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple
from dataclasses import dataclass
import logging

# Phase 5.1-5.3: Memory Enhancement
from src.self_improvement.meta_memory import MetaMemoryManager, MemoryImportance
from src.self_improvement.procedural_memory import ProceduralMemoryManager, ProcedureType
from src.memory.context_aware_retrieval import ContextAwareRetriever, ContextDimension

# Phase 5.4-5.7: Advanced Learning
from src.self_improvement.transfer_learning import TransferLearningManager, TaskFamily
from src.self_improvement.reinforcement_learning import ReinforcementLearningManager, RewardSignal
from src.self_improvement.meta_learning import MetaLearningManager
from src.self_improvement.adaptive_forgetting import AdaptiveForgetfulnessManager, ForgetfulnessLevel


logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionTrace:
    """Record of a single task execution for learning."""
    task_id: str
    task_family: str
    input_query: str
    execution_time_ms: float
    success: bool
    output_quality: float  # 0-1
    tools_used: List[str]
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class Phase5IntegrationManager:
    """
    Unified manager for all Phase 5 learning and memory systems.
    
    Coordinates:
    - Memory systems (Meta, Procedural, Context-Aware)
    - Learning systems (Transfer, RL, Meta-Learning)
    - Optimization (Adaptive Forgetting)
    """

    def __init__(self, agent_id: str = "default_agent"):
        """Initialize all Phase 5 systems."""
        self.agent_id = agent_id
        
        # Phase 5.1-5.3: Memory Systems
        self.meta_memory = MetaMemoryManager()
        self.procedural_memory = ProceduralMemoryManager()
        self.context_retriever = ContextAwareRetriever()
        
        # Phase 5.4-5.7: Learning Systems
        self.transfer_learning = TransferLearningManager()
        self.rl_manager = ReinforcementLearningManager()
        self.meta_learning = MetaLearningManager()
        self.adaptive_forgetting = AdaptiveForgetfulnessManager(
            forgetfulness_level=ForgetfulnessLevel.BALANCED
        )
        
        # Execution tracking
        self.execution_traces: List[TaskExecutionTrace] = []
        self.decisions: Dict[str, Any] = {}
        
        logger.info(f"Phase 5 Integration Manager initialized for agent: {agent_id}")

    # ========================================================================
    # Memory Management Methods
    # ========================================================================

    def record_solution(
        self,
        task_id: str,
        solution: str,
        importance: float = 0.7,
        tags: Optional[List[str]] = None,
    ):
        """
        Record a successful solution in memory systems.
        
        Args:
            task_id: Unique task identifier
            solution: The solution/answer
            importance: How important is this solution? (0-1)
            tags: Tags for categorization
        """
        memory_key = f"solution_{task_id}"
        
        # Record in Meta Memory
        self.meta_memory.record_memory(
            memory_id=memory_key,
            content=solution,
            memory_type="solution",
            importance=MemoryImportance.HIGH if importance > 0.7 else MemoryImportance.MEDIUM,
        )
        
        # Register in Context Retriever
        self.context_retriever.index_memory(
            memory_id=memory_key,
            content=solution,
            context={"task_id": task_id, "tags": tags or []},
        )
        
        # Record access for Adaptive Forgetting
        self.adaptive_forgetting.register_memory(
            memory_id=memory_key,
            importance=importance
        )
        
        logger.debug(f"Solution recorded for task {task_id}")

    def retrieve_similar_solutions(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Retrieve similar solutions from memory.
        
        Args:
            query: Search query
            task_type: Optional task type filter
            top_k: Number of results to return
            
        Returns:
            List of (solution, similarity_score) tuples
        """
        results = self.context_retriever.retrieve(
            query=query,
            context_filters={"task_type": task_type} if task_type else {},
            top_k=top_k,
        )
        
        # Record retrieval access
        for result in results:
            memory_id = result.memory_id
            if memory_id in self.procedural_memory.cache:
                self.adaptive_forgetting.record_access(memory_id)
        
        return [(r.content, r.relevance_score) for r in results]

    # ========================================================================
    # Procedural Memory & Caching
    # ========================================================================

    def cache_procedure(
        self,
        procedure_id: str,
        steps: List[str],
        parameters: Dict[str, Any],
        execution_time_ms: float,
        success_rate: float,
    ):
        """Cache a successful procedure for reuse."""
        self.procedural_memory.create_procedure(
            procedure_id=procedure_id,
            procedure_type=ProcedureType.DATA_PROCESSING,
            steps=steps,
            tools_required=[],
            estimated_duration_ms=execution_time_ms,
            success_rate=success_rate,
        )
        
        # Cache parameters
        self.procedural_memory.cache_parameter_set(
            procedure_id=procedure_id,
            parameters=parameters,
        )

    def get_recommended_procedure(
        self,
        task_description: str,
        similarity_threshold: float = 0.6,
    ) -> Optional[Tuple[str, List[str], Dict[str, Any]]]:
        """
        Get a recommended procedure for similar tasks.
        
        Returns:
            (procedure_id, steps, parameters) or None
        """
        procedures = self.procedural_memory.find_similar_procedures(
            description=task_description,
            min_similarity=similarity_threshold,
        )
        
        if procedures:
            best = max(procedures, key=lambda p: p.get_reliability_score())
            params = self.procedural_memory.recommend_parameters(
                procedure_id=best.procedure_id,
                context={},
            )
            return (best.procedure_id, best.steps, params)
        
        return None

    # ========================================================================
    # Transfer Learning
    # ========================================================================

    def register_task(
        self,
        task_id: str,
        task_family: str,
        input_type: str,
        output_type: str,
        complexity_score: float,
        processing_time_ms: float,
        success_rate: float,
        tools_required: List[str],
    ):
        """Register a task for transfer learning."""
        self.transfer_learning.register_task(
            task_id=task_id,
            task_family=task_family,
            input_type=input_type,
            output_type=output_type,
            complexity_score=complexity_score,
            processing_time_ms=processing_time_ms,
            success_rate=success_rate,
            tools_required=tools_required,
        )

    def recommend_knowledge_transfer(
        self,
        target_task_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Recommend transferable knowledge for a new task.
        
        Returns:
            List of knowledge transfer recommendations
        """
        return self.transfer_learning.recommend_knowledge_transfer(
            target_task_id=target_task_id
        )

    # ========================================================================
    # Reinforcement Learning
    # ========================================================================

    def record_execution_trace(
        self,
        task_id: str,
        task_family: str,
        query: str,
        execution_time_ms: float,
        success: bool,
        output_quality: float,
        tools_used: List[str],
        error_message: Optional[str] = None,
    ) -> TaskExecutionTrace:
        """
        Record an execution trace for reinforcement learning.
        
        Args:
            task_id: Task identifier
            task_family: Task family/domain
            query: Input query
            execution_time_ms: Execution duration
            success: Was task successful?
            output_quality: Quality score (0-1)
            tools_used: List of tools used
            error_message: Error message if failed
            
        Returns:
            TaskExecutionTrace object
        """
        trace = TaskExecutionTrace(
            task_id=task_id,
            task_family=task_family,
            input_query=query,
            execution_time_ms=execution_time_ms,
            success=success,
            output_quality=output_quality,
            tools_used=tools_used,
            error_message=error_message,
        )
        
        self.execution_traces.append(trace)
        
        # Record decision for RL
        decision = self.rl_manager.record_decision(
            context={
                "task_family": task_family,
                "query_length": len(query),
                "tools_count": len(tools_used),
            },
            action_chosen=f"approach_{task_family}",
            alternatives=[f"approach_alternative_{i}" for i in range(2)],
        )
        
        self.decisions[task_id] = decision
        
        # Add rewards
        if success:
            self.rl_manager.add_reward(
                decision_id=decision.decision_id,
                reward_signal=RewardSignal.TASK_SUCCESS,
                value=1.0,
            )
        
        # Time-based reward
        time_reward = min(1.0, 1000.0 / max(execution_time_ms, 1.0))
        self.rl_manager.add_reward(
            decision_id=decision.decision_id,
            reward_signal=RewardSignal.EXECUTION_TIME,
            value=time_reward,
        )
        
        # Quality reward
        self.rl_manager.add_reward(
            decision_id=decision.decision_id,
            reward_signal=RewardSignal.QUALITY,
            value=output_quality,
        )
        
        return trace

    def learn_from_experience(self):
        """Trigger reinforcement learning from recorded experience."""
        self.rl_manager.learn_from_experience()
        logger.info(f"RL learning completed. Experience entries: {len(self.rl_manager.experience_replay)}")

    # ========================================================================
    # Meta Learning
    # ========================================================================

    def get_optimal_learning_config(
        self,
        task_id: str,
        task_family: str,
        complexity: float,
    ):
        """Get optimal learning configuration for a task."""
        from src.self_improvement.meta_learning import TaskMetaFeatures
        
        features = TaskMetaFeatures(
            task_id=task_id,
            task_family=task_family,
            complexity=complexity,
            data_volume="medium",
            success_rate=0.8,
            variability=0.5,
            learning_curve_slope=0.7,
            error_rate=0.2,
        )
        
        config = self.meta_learning.create_optimal_config(
            task_family=task_family,
            features=features,
        )
        
        return config

    # ========================================================================
    # Adaptive Forgetting
    # ========================================================================

    def review_and_consolidate_memories(self):
        """
        Review memories and consolidate important ones.
        Should be called periodically.
        """
        # Get memories due for review
        reviews_due = self.adaptive_forgetting.get_review_schedule()
        
        for memory_id in reviews_due:
            # Update review record
            self.adaptive_forgetting.mark_as_consolidated(memory_id)
        
        # Prune forgotten memories
        forgotten = self.adaptive_forgetting.prune_forgotten_memories()
        
        if forgotten:
            logger.info(f"Pruned {len(forgotten)} forgotten memories")
        
        return reviews_due, forgotten

    # ========================================================================
    # Statistics & Monitoring
    # ========================================================================

    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get comprehensive learning statistics."""
        successful_traces = [t for t in self.execution_traces if t.success]
        failed_traces = [t for t in self.execution_traces if not t.success]
        
        avg_quality = (
            sum(t.output_quality for t in successful_traces) / len(successful_traces)
            if successful_traces else 0.0
        )
        
        avg_time = (
            sum(t.execution_time_ms for t in self.execution_traces) / len(self.execution_traces)
            if self.execution_traces else 0.0
        )
        
        return {
            "total_executions": len(self.execution_traces),
            "successful": len(successful_traces),
            "failed": len(failed_traces),
            "success_rate": len(successful_traces) / len(self.execution_traces) if self.execution_traces else 0.0,
            "average_quality": avg_quality,
            "average_execution_time_ms": avg_time,
            "systems_active": 7,  # All Phase 5 systems
            "rl_decisions_recorded": len(self.rl_manager.decisions),
            "memories_recorded": len(self.execution_traces),
        }

    def log_statistics(self):
        """Log current learning statistics."""
        stats = self.get_learning_statistics()
        logger.info(f"Learning Statistics: {stats}")


# Global instance
_phase5_manager: Optional[Phase5IntegrationManager] = None


def get_phase5_manager() -> Phase5IntegrationManager:
    """Get or create the global Phase 5 integration manager."""
    global _phase5_manager
    if _phase5_manager is None:
        _phase5_manager = Phase5IntegrationManager()
    return _phase5_manager


def initialize_phase5(agent_id: str = "default_agent") -> Phase5IntegrationManager:
    """Initialize Phase 5 integration manager."""
    global _phase5_manager
    _phase5_manager = Phase5IntegrationManager(agent_id=agent_id)
    return _phase5_manager
