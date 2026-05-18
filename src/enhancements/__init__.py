"""
Package initialization for memory enhancements (Phase 5).
"""

from src.self_improvement.meta_memory import (
    MetaMemoryManager,
    MemoryQualityScore,
    MemoryImportance,
    MemoryRetentionPolicy,
    MemoryConsolidation,
)

from src.self_improvement.procedural_memory import (
    ProceduralMemoryManager,
    ProcedurePattern,
    ProcedureType,
    ExecutionStep,
    ParameterPattern,
    TimeSeriesMemory,
)

from src.memory.context_aware_retrieval import (
    ContextAwareRetriever,
    ContextVector,
    ContextDimension,
    ContextualMemory,
    RetrievalResult,
)

from src.self_improvement.adaptive_forgetting import (
    AdaptiveForgetfulnessManager,
    ForgetfulnessLevel,
    ForgetfullnessCurve,
    SpacedRepetition,
)

from src.self_improvement.transfer_learning import (
    TransferLearningManager,
    TaskFamily,
    TaskCharacteristics,
    TransferableKnowledge,
    TransferAttempt,
)

from src.self_improvement.reinforcement_learning import (
    ReinforcementLearningManager,
    RewardSignal,
    Reward,
    Decision,
    Policy,
    ExperienceEntry,
)

from src.self_improvement.meta_learning import (
    MetaLearningManager,
    LearningStrategy,
    TaskMetaFeatures,
    LearningConfiguration,
    MetaFeatureAnalysis,
)

__all__ = [
    # Meta Memory
    "MetaMemoryManager",
    "MemoryQualityScore",
    "MemoryImportance",
    "MemoryRetentionPolicy",
    "MemoryConsolidation",
    # Procedural Memory
    "ProceduralMemoryManager",
    "ProcedurePattern",
    "ProcedureType",
    "ExecutionStep",
    "ParameterPattern",
    "TimeSeriesMemory",
    # Context-Aware Retrieval
    "ContextAwareRetriever",
    "ContextVector",
    "ContextDimension",
    "ContextualMemory",
    "RetrievalResult",
    # Adaptive Forgetting
    "AdaptiveForgetfulnessManager",
    "ForgetfulnessLevel",
    "ForgetfullnessCurve",
    "SpacedRepetition",
    # Transfer Learning
    "TransferLearningManager",
    "TaskFamily",
    "TaskCharacteristics",
    "TransferableKnowledge",
    "TransferAttempt",
    # Reinforcement Learning
    "ReinforcementLearningManager",
    "RewardSignal",
    "Reward",
    "Decision",
    "Policy",
    "ExperienceEntry",
    # Meta Learning
    "MetaLearningManager",
    "LearningStrategy",
    "TaskMetaFeatures",
    "LearningConfiguration",
    "MetaFeatureAnalysis",
]
