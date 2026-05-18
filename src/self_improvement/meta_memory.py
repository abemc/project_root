"""
Meta Memory System: Evaluates and improves memory quality.

This module implements adaptive memory management that assesses the quality,
reliability, and utility of stored memories. It automatically adjusts retention
policies based on how often memories are accessed and their demonstrated value
in decision-making.

Key Features:
- Memory quality scoring based on confidence, usage, and recency
- Adaptive retention policies that adjust based on importance
- Automatic pruning of low-quality or obsolete memories
- Memory consolidation to improve clarity and completeness
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib


class MemoryImportance(Enum):
    """Importance levels for memory retention policies."""
    CRITICAL = 1.0      # Never auto-delete
    HIGH = 0.8          # Retain 90+ days
    NORMAL = 0.5        # Retain 30-60 days
    LOW = 0.2           # Retain 7-14 days


@dataclass
class MemoryQualityScore:
    """Quantifies the quality and reliability of a stored memory."""
    memory_id: str
    confidence: float           # 0-1: How reliable is this memory?
    usage_count: int            # How many times has it been accessed?
    last_accessed: datetime     # When was it last used?
    access_frequency: float     # Accesses per day
    accuracy_rating: float      # 0-1: User-rated accuracy (if available)
    relevance_score: float      # 0-1: How often does it appear in queries?
    
    def compute_quality(self) -> float:
        """
        Compute overall quality score (0-1).
        
        Factors:
        - Confidence (40%): How reliable is the memory?
        - Usage (30%): How frequently is it accessed?
        - Recency (20%): Is it recent enough to be relevant?
        - Accuracy (10%): Has it been validated?
        
        Returns:
            Quality score (0-1).
        """
        recency_factor = self._compute_recency_factor()
        quality = (
            (self.confidence * 0.40) +
            (min(self.usage_count / 100, 1.0) * 0.30) +
            (recency_factor * 0.20) +
            (self.accuracy_rating * 0.10)
        )
        return min(max(quality, 0.0), 1.0)
    
    def _compute_recency_factor(self) -> float:
        """Compute recency factor based on access time."""
        days_since_access = (datetime.now() - self.last_accessed).days
        # Exponential decay: full score if < 30 days, decays after
        if days_since_access <= 30:
            return 1.0
        else:
            decay_rate = 0.95 ** (days_since_access - 30)
            return max(decay_rate, 0.1)
    
    def should_consolidate(self) -> bool:
        """Determine if memory should be consolidated (improved)."""
        # Consolidate if: frequently used (count > 10) but low confidence
        return self.usage_count >= 10 and self.confidence < 0.8
    
    def consolidation_suggestion(self) -> str:
        """Generate a suggestion for improving this memory."""
        if self.confidence < 0.5:
            return "Consider re-validating this memory with a new information source."
        elif self.usage_count > 50 and self.accuracy_rating < 0.9:
            return "This frequently-used memory has moderate accuracy. Refine it."
        else:
            return "Memory quality is acceptable."


@dataclass
class MemoryRetentionPolicy:
    """Defines how long and under what conditions a memory should be retained."""
    memory_id: str
    importance: MemoryImportance
    base_retention_days: int     # Default retention period
    last_reviewed: datetime
    access_velocity: float        # Accesses per day
    
    def compute_retention_days(self, quality_score: float) -> int:
        """
        Compute actual retention days based on importance and quality.
        
        Algorithm:
        - If importance is CRITICAL: retain indefinitely (10+ years)
        - If quality_score is high (>0.8): extend by 50%
        - If quality_score is low (<0.3): reduce by 50%
        - If usage is declining: reduce retention
        
        Args:
            quality_score: Memory quality from MemoryQualityScore.compute_quality()
            
        Returns:
            Number of days to retain this memory.
        """
        if self.importance == MemoryImportance.CRITICAL:
            return 3650  # ~10 years
        
        base = self.base_retention_days
        
        # Adjust based on quality
        if quality_score > 0.8:
            base = int(base * 1.5)
        elif quality_score < 0.3:
            base = int(base * 0.5)
        
        # Adjust based on access velocity (declining usage = shorter retention)
        if self.access_velocity < 0.1:  # Less than 1 access per 10 days
            base = int(base * 0.7)
        
        return max(base, 1)  # At least 1 day
    
    def should_mark_for_review(self) -> bool:
        """Determine if memory should be reviewed by user."""
        days_since_review = (datetime.now() - self.last_reviewed).days
        return days_since_review > 60


@dataclass
class MemoryConsolidation:
    """Represents an improvement to a stored memory."""
    memory_id: str
    original_content: str
    improved_content: str
    consolidation_type: str     # "refinement" | "validation" | "expansion"
    confidence_increase: float  # 0-1: How much did confidence improve?
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "memory_id": self.memory_id,
            "original": self.original_content,
            "improved": self.improved_content,
            "type": self.consolidation_type,
            "confidence_gain": self.confidence_increase,
            "timestamp": self.timestamp.isoformat(),
        }


class MetaMemoryManager:
    """
    Manages the quality and retention of stored memories.
    
    Responsibilities:
    - Track memory quality metrics
    - Recommend consolidation (improvement) of low-quality memories
    - Manage retention policies based on importance and usage
    - Automatically prune obsolete memories
    - Generate memory health reports
    """
    
    def __init__(self):
        """Initialize meta-memory manager."""
        self.memory_quality_scores: Dict[str, MemoryQualityScore] = {}
        self.retention_policies: Dict[str, MemoryRetentionPolicy] = {}
        self.consolidation_history: List[MemoryConsolidation] = []
        self.deletion_log: List[Tuple[str, str, datetime]] = []  # (id, reason, time)
    
    def register_memory_access(self, memory_id: str, confidence: float = 1.0):
        """
        Record that a memory was accessed.
        
        Args:
            memory_id: The identifier of the accessed memory.
            confidence: How confident are we in this memory? (0-1)
        """
        if memory_id not in self.memory_quality_scores:
            self.memory_quality_scores[memory_id] = MemoryQualityScore(
                memory_id=memory_id,
                confidence=confidence,
                usage_count=1,
                last_accessed=datetime.now(),
                access_frequency=1.0,
                accuracy_rating=0.9,
                relevance_score=0.5,
            )
        else:
            score = self.memory_quality_scores[memory_id]
            score.usage_count += 1
            score.last_accessed = datetime.now()
            score.confidence = max(score.confidence, confidence)
            # Update access frequency (exponential moving average)
            score.access_frequency = (score.access_frequency * 0.8) + (confidence * 0.2)
    
    def set_memory_importance(self, memory_id: str, importance: MemoryImportance):
        """
        Set the importance level for a memory.
        
        Args:
            memory_id: The identifier of the memory.
            importance: Importance level.
        """
        if memory_id not in self.retention_policies:
            base_days = {
                MemoryImportance.CRITICAL: 365,
                MemoryImportance.HIGH: 90,
                MemoryImportance.NORMAL: 45,
                MemoryImportance.LOW: 14,
            }[importance]
            
            self.retention_policies[memory_id] = MemoryRetentionPolicy(
                memory_id=memory_id,
                importance=importance,
                base_retention_days=base_days,
                last_reviewed=datetime.now(),
                access_velocity=0.5,
            )
        else:
            self.retention_policies[memory_id].importance = importance
    
    def get_memory_health(self, memory_id: str) -> Dict:
        """
        Get comprehensive health report for a memory.
        
        Args:
            memory_id: The identifier of the memory.
            
        Returns:
            Dictionary with health metrics.
        """
        if memory_id not in self.memory_quality_scores:
            return {"error": f"Memory {memory_id} not found"}
        
        quality = self.memory_quality_scores[memory_id]
        policy = self.retention_policies.get(memory_id)
        
        quality_score = quality.compute_quality()
        
        return {
            "memory_id": memory_id,
            "quality_score": quality_score,
            "confidence": quality.confidence,
            "usage_count": quality.usage_count,
            "access_frequency": quality.access_frequency,
            "accuracy_rating": quality.accuracy_rating,
            "days_since_access": (datetime.now() - quality.last_accessed).days,
            "importance": policy.importance.name if policy else "UNKNOWN",
            "retention_days": policy.compute_retention_days(quality_score) if policy else 0,
            "should_consolidate": quality.should_consolidate(),
            "consolidation_suggestion": quality.consolidation_suggestion(),
            "should_review": policy.should_mark_for_review() if policy else False,
        }
    
    def get_consolidation_candidates(self, threshold: float = 0.6) -> List[str]:
        """
        Identify memories that should be consolidated (improved).
        
        Args:
            threshold: Quality score threshold. Memories below this are candidates.
            
        Returns:
            List of memory IDs that should be consolidated.
        """
        candidates = []
        for memory_id, quality in self.memory_quality_scores.items():
            if quality.compute_quality() < threshold and quality.should_consolidate():
                candidates.append(memory_id)
        return sorted(candidates)
    
    def record_consolidation(
        self,
        memory_id: str,
        original: str,
        improved: str,
        consolidation_type: str,
        confidence_gain: float,
    ) -> MemoryConsolidation:
        """
        Record that a memory has been improved.
        
        Args:
            memory_id: The identifier of the memory.
            original: Original memory content.
            improved: Improved memory content.
            consolidation_type: Type of improvement (refinement|validation|expansion).
            confidence_gain: How much confidence improved (0-1).
            
        Returns:
            The consolidation record.
        """
        consolidation = MemoryConsolidation(
            memory_id=memory_id,
            original_content=original,
            improved_content=improved,
            consolidation_type=consolidation_type,
            confidence_increase=confidence_gain,
        )
        self.consolidation_history.append(consolidation)
        
        # Improve the quality score
        if memory_id in self.memory_quality_scores:
            self.memory_quality_scores[memory_id].confidence += confidence_gain
            self.memory_quality_scores[memory_id].confidence = min(1.0, 
                self.memory_quality_scores[memory_id].confidence
            )
        
        return consolidation
    
    def prune_obsolete_memories(self) -> List[str]:
        """
        Remove memories that have exceeded their retention period.
        
        Returns:
            List of deleted memory IDs.
        """
        deleted = []
        now = datetime.now()
        
        for memory_id, quality in list(self.memory_quality_scores.items()):
            policy = self.retention_policies.get(memory_id)
            if not policy:
                continue
            
            quality_score = quality.compute_quality()
            retention_days = policy.compute_retention_days(quality_score)
            
            if (now - quality.last_accessed).days > retention_days:
                deleted.append(memory_id)
                del self.memory_quality_scores[memory_id]
                self.deletion_log.append((
                    memory_id,
                    f"Exceeded retention period: {retention_days} days",
                    now,
                ))
        
        return deleted
    
    def get_statistics(self) -> Dict:
        """
        Get overall statistics about memory system health.
        
        Returns:
            Dictionary with statistics.
        """
        if not self.memory_quality_scores:
            return {
                "total_memories": 0,
                "average_quality": 0.0,
                "memories_needing_consolidation": 0,
                "memories_needing_review": 0,
                "total_deletions": 0,
            }
        
        quality_scores = [q.compute_quality() for q in self.memory_quality_scores.values()]
        consolidation_candidates = self.get_consolidation_candidates()
        
        review_count = 0
        for memory_id, policy in self.retention_policies.items():
            if policy.should_mark_for_review():
                review_count += 1
        
        return {
            "total_memories": len(self.memory_quality_scores),
            "average_quality": sum(quality_scores) / len(quality_scores),
            "quality_distribution": {
                "high": sum(1 for q in quality_scores if q > 0.8),
                "medium": sum(1 for q in quality_scores if 0.4 < q <= 0.8),
                "low": sum(1 for q in quality_scores if q <= 0.4),
            },
            "memories_needing_consolidation": len(consolidation_candidates),
            "memories_needing_review": review_count,
            "total_consolidations": len(self.consolidation_history),
            "total_deletions": len(self.deletion_log),
        }
    
    def export_report(self, filepath: str):
        """
        Export comprehensive memory health report to JSON.
        
        Args:
            filepath: Output file path.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
            "consolidation_candidates": self.get_consolidation_candidates(),
            "consolidation_history": [
                c.to_dict() for c in self.consolidation_history[-100:]  # Last 100
            ],
            "deletion_log": [
                {
                    "memory_id": d[0],
                    "reason": d[1],
                    "timestamp": d[2].isoformat(),
                }
                for d in self.deletion_log[-100:]  # Last 100
            ],
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
