"""
Meta Learning: Learn how to learn more efficiently.

This module implements meta-learning (learning to learn) mechanisms that help
the AI agent improve its own learning processes. It adjusts learning strategies
based on task characteristics and adapts to new domains faster.

Key Features:
- Adaptive learning rate per task type
- Feature selection for learning
- Algorithm selection (when to use which learning approach)
- Task-specific hyperparameter optimization
- Meta-features for domain adaptation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
import json


class LearningStrategy(Enum):
    """Different learning approaches available."""
    ERROR_LEARNING = "error_learning"           # Learn from mistakes
    PATTERN_EXTRACTION = "pattern_extraction"   # Find success patterns
    TRANSFER_LEARNING = "transfer_learning"     # Apply from other domains
    REINFORCEMENT = "reinforcement"             # Reward-based learning
    PROCEDURAL = "procedural"                   # Cache procedures


@dataclass
class TaskMetaFeatures:
    """High-level features of a task that influence learning."""
    task_id: str
    task_family: str                  # Domain (data analysis, etc.)
    complexity: float                 # 0-1: Task complexity
    data_volume: str                  # small | medium | large
    success_rate: float               # Historical success (0-1)
    variability: float                # 0-1: How much do conditions vary?
    learning_curve_slope: float       # How fast does performance improve?
    error_rate: float                 # 0-1: Frequency of errors


@dataclass
class LearningConfiguration:
    """Configuration for learning on a specific task."""
    config_id: str
    task_family: str
    primary_strategy: LearningStrategy
    secondary_strategies: List[LearningStrategy]
    learning_rate: float              # 0-1: Speed of learning
    feature_selection: List[str]      # Relevant features for learning
    hyperparameters: Dict[str, Any]   # Algorithm-specific params
    success_rate: float               # 0-1: How well does this config work?
    application_count: int = 0
    
    def effectiveness(self) -> float:
        """
        Compute effectiveness of this configuration (0-1).
        
        Factors:
        - Success rate (70%)
        - Application frequency (20%)
        - Recency (10%)
        
        Returns:
            Effectiveness score (0-1).
        """
        freq_factor = min(self.application_count / 50, 1.0)
        
        # Assume recent = more effective
        recency_factor = 0.9  # Simplified
        
        effectiveness = (
            (self.success_rate * 0.7) +
            (freq_factor * 0.2) +
            (recency_factor * 0.1)
        )
        return min(max(effectiveness, 0.0), 1.0)


@dataclass
class MetaFeatureAnalysis:
    """Analysis of meta-features to guide learning."""
    task_id: str
    meta_features: TaskMetaFeatures
    identified_learning_needs: List[str]
    recommended_strategies: List[Tuple[LearningStrategy, float]]  # (strategy, relevance)
    recommended_learning_rate: float
    critical_features: List[str]      # Most important features to learn
    recommended_algorithm: LearningStrategy


class MetaLearningManager:
    """
    Manages meta-learning: learning how to learn.
    
    Responsibilities:
    - Analyze task characteristics
    - Recommend optimal learning strategies
    - Adapt learning rates per task type
    - Select features for learning
    - Evaluate learning effectiveness
    - Optimize learning algorithms
    """
    
    def __init__(self):
        """Initialize meta-learning manager."""
        self.task_meta_features: Dict[str, TaskMetaFeatures] = {}
        self.learning_configs: Dict[str, LearningConfiguration] = {}
        self.family_configs: Dict[str, LearningConfiguration] = {}  # family → best config
        self.meta_analyses: List[MetaFeatureAnalysis] = []
        
        # Pre-defined strategy effectiveness per task family
        self.strategy_effectiveness_matrix: Dict[str, Dict[LearningStrategy, float]] = {
            "data_analysis": {
                LearningStrategy.PATTERN_EXTRACTION: 0.9,
                LearningStrategy.PROCEDURAL: 0.85,
                LearningStrategy.ERROR_LEARNING: 0.7,
                LearningStrategy.TRANSFER_LEARNING: 0.75,
                LearningStrategy.REINFORCEMENT: 0.6,
            },
            "text_processing": {
                LearningStrategy.ERROR_LEARNING: 0.85,
                LearningStrategy.PATTERN_EXTRACTION: 0.8,
                LearningStrategy.TRANSFER_LEARNING: 0.9,
                LearningStrategy.PROCEDURAL: 0.7,
                LearningStrategy.REINFORCEMENT: 0.65,
            },
            "system_admin": {
                LearningStrategy.ERROR_LEARNING: 0.95,
                LearningStrategy.PROCEDURAL: 0.88,
                LearningStrategy.PATTERN_EXTRACTION: 0.75,
                LearningStrategy.TRANSFER_LEARNING: 0.7,
                LearningStrategy.REINFORCEMENT: 0.65,
            },
            "api_integration": {
                LearningStrategy.TRANSFER_LEARNING: 0.85,
                LearningStrategy.ERROR_LEARNING: 0.8,
                LearningStrategy.PROCEDURAL: 0.82,
                LearningStrategy.PATTERN_EXTRACTION: 0.7,
                LearningStrategy.REINFORCEMENT: 0.75,
            },
        }
    
    def analyze_task(
        self,
        task_id: str,
        task_family: str,
        complexity: float,
        data_volume: str,
        success_rate: float,
        variability: float,
        learning_curve_slope: float,
        error_rate: float,
    ) -> MetaFeatureAnalysis:
        """
        Analyze task characteristics and recommend learning strategy.
        
        Args:
            task_id: Task identifier.
            task_family: Domain/family.
            complexity: Task complexity (0-1).
            data_volume: Data size.
            success_rate: Historical success (0-1).
            variability: Condition variability (0-1).
            learning_curve_slope: How fast improvement happens.
            error_rate: Error frequency (0-1).
            
        Returns:
            MetaFeatureAnalysis with recommendations.
        """
        meta_features = TaskMetaFeatures(
            task_id=task_id,
            task_family=task_family,
            complexity=complexity,
            data_volume=data_volume,
            success_rate=success_rate,
            variability=variability,
            learning_curve_slope=learning_curve_slope,
            error_rate=error_rate,
        )
        
        self.task_meta_features[task_id] = meta_features
        
        # Identify learning needs
        learning_needs = []
        if error_rate > 0.3:
            learning_needs.append("High error rate - focus on error learning")
        if variability > 0.7:
            learning_needs.append("High variability - need robust patterns")
        if complexity > 0.8:
            learning_needs.append("Complex task - procedural caching recommended")
        if learning_curve_slope < 0.5:
            learning_needs.append("Slow learning - transfer learning may help")
        
        # Recommend strategies based on task family
        recommended_strategies = self._recommend_strategies(task_family)
        
        # Recommend learning rate
        recommended_lr = self._compute_learning_rate(
            complexity, error_rate, learning_curve_slope
        )
        
        # Identify critical features
        critical_features = self._identify_critical_features(meta_features)
        
        # Select best algorithm
        best_algorithm = max(
            recommended_strategies,
            key=lambda x: x[1]
        )[0]
        
        analysis = MetaFeatureAnalysis(
            task_id=task_id,
            meta_features=meta_features,
            identified_learning_needs=learning_needs,
            recommended_strategies=recommended_strategies,
            recommended_learning_rate=recommended_lr,
            critical_features=critical_features,
            recommended_algorithm=best_algorithm,
        )
        
        self.meta_analyses.append(analysis)
        return analysis
    
    def _recommend_strategies(
        self,
        task_family: str,
    ) -> List[Tuple[LearningStrategy, float]]:
        """
        Recommend learning strategies for a task family.
        
        Args:
            task_family: Task domain.
            
        Returns:
            List of (strategy, relevance) tuples.
        """
        if task_family not in self.strategy_effectiveness_matrix:
            # Default strategy order for unknown families
            default_strategies = [
                (LearningStrategy.ERROR_LEARNING, 0.8),
                (LearningStrategy.PATTERN_EXTRACTION, 0.75),
                (LearningStrategy.TRANSFER_LEARNING, 0.7),
                (LearningStrategy.PROCEDURAL, 0.65),
                (LearningStrategy.REINFORCEMENT, 0.6),
            ]
            return default_strategies
        
        effectiveness = self.strategy_effectiveness_matrix[task_family]
        strategies = sorted(
            effectiveness.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return strategies
    
    def _compute_learning_rate(
        self,
        complexity: float,
        error_rate: float,
        learning_curve_slope: float,
    ) -> float:
        """
        Compute recommended learning rate.
        
        Args:
            complexity: Task complexity (0-1).
            error_rate: Error frequency (0-1).
            learning_curve_slope: Improvement rate.
            
        Returns:
            Recommended learning rate (0-1).
        """
        # Complex tasks: slower learning (0.05-0.15)
        # Simple tasks: faster learning (0.15-0.3)
        base_lr = 0.1 if complexity < 0.5 else 0.05
        
        # High error rate: slower learning
        if error_rate > 0.5:
            base_lr *= 0.7
        
        # Fast learning curve: can learn faster
        if learning_curve_slope > 0.8:
            base_lr *= 1.2
        
        return min(max(base_lr, 0.01), 0.3)
    
    def _identify_critical_features(
        self,
        meta_features: TaskMetaFeatures,
    ) -> List[str]:
        """
        Identify features most important for learning.
        
        Args:
            meta_features: Task meta-features.
            
        Returns:
            List of critical feature names.
        """
        critical = []
        
        if meta_features.complexity > 0.7:
            critical.append("task_structure")
        
        if meta_features.error_rate > 0.4:
            critical.append("error_patterns")
        
        if meta_features.variability > 0.6:
            critical.append("contextual_adaptation")
        
        if meta_features.data_volume == "large":
            critical.append("resource_efficiency")
        
        critical.append("success_signals")
        
        return critical
    
    def create_optimal_config(
        self,
        task_family: str,
        analysis: MetaFeatureAnalysis,
    ) -> LearningConfiguration:
        """
        Create optimal learning configuration for a task.
        
        Args:
            task_family: Task domain.
            analysis: Meta-feature analysis.
            
        Returns:
            Optimal LearningConfiguration.
        """
        config_id = f"{task_family}_{datetime.now().timestamp():.0f}"
        
        strategies = analysis.recommended_strategies
        primary = strategies[0][0] if strategies else LearningStrategy.ERROR_LEARNING
        secondary = [s[0] for s in strategies[1:3]] if len(strategies) > 1 else []
        
        config = LearningConfiguration(
            config_id=config_id,
            task_family=task_family,
            primary_strategy=primary,
            secondary_strategies=secondary,
            learning_rate=analysis.recommended_learning_rate,
            feature_selection=analysis.critical_features,
            hyperparameters={
                "batch_size": 32,
                "num_epochs": 10,
                "early_stopping_patience": 5,
            },
            success_rate=0.0,  # Will update as used
        )
        
        self.learning_configs[config_id] = config
        
        # Update family-level best config
        if task_family not in self.family_configs or \
           config.effectiveness() > self.family_configs[task_family].effectiveness():
            self.family_configs[task_family] = config
        
        return config
    
    def record_config_performance(
        self,
        config_id: str,
        task_success_rate: float,
    ):
        """
        Record performance of a learning configuration.
        
        Args:
            config_id: Configuration ID.
            task_success_rate: Success rate achieved (0-1).
        """
        if config_id not in self.learning_configs:
            return
        
        config = self.learning_configs[config_id]
        
        # Update success rate (exponential moving average)
        alpha = 0.1
        config.success_rate = (
            (config.success_rate * (1 - alpha)) +
            (task_success_rate * alpha)
        )
        config.application_count += 1
    
    def get_best_config_for_family(self, task_family: str) -> Optional[LearningConfiguration]:
        """Get the best configuration for a task family."""
        return self.family_configs.get(task_family)
    
    def get_meta_learning_statistics(self) -> Dict:
        """Get overall meta-learning statistics."""
        if not self.task_meta_features:
            return {
                "tasks_analyzed": 0,
                "configs_created": 0,
                "family_coverage": 0,
            }
        
        families = set(f.task_family for f in self.task_meta_features.values())
        
        avg_config_effectiveness = 0.0
        if self.learning_configs:
            configs = self.learning_configs.values()
            avg_config_effectiveness = sum(c.effectiveness() for c in configs) / len(configs)
        
        return {
            "tasks_analyzed": len(self.task_meta_features),
            "configs_created": len(self.learning_configs),
            "family_coverage": len(families),
            "avg_config_effectiveness": avg_config_effectiveness,
            "meta_analyses": len(self.meta_analyses),
        }
    
    def export_meta_analysis_report(self, filepath: str):
        """
        Export meta-learning analysis to JSON.
        
        Args:
            filepath: Output file path.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.get_meta_learning_statistics(),
            "best_configs_per_family": {
                family: {
                    "primary_strategy": config.primary_strategy.value,
                    "learning_rate": config.learning_rate,
                    "effectiveness": config.effectiveness(),
                    "applications": config.application_count,
                }
                for family, config in self.family_configs.items()
            },
            "strategy_effectiveness": {
                family: {
                    strategy.value: effectiveness
                    for strategy, effectiveness in strategies.items()
                }
                for family, strategies in self.strategy_effectiveness_matrix.items()
            },
            "recent_analyses": [
                {
                    "task_id": a.task_id,
                    "task_family": a.meta_features.task_family,
                    "recommended_algorithm": a.recommended_algorithm.value,
                    "learning_rate": a.recommended_learning_rate,
                }
                for a in self.meta_analyses[-20:]  # Last 20
            ],
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
