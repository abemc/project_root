"""
Adaptive Forgetting: Intelligent memory retention and automatic pruning.

This module implements adaptive forgetting mechanisms that automatically manage
memory lifecycle based on importance, usage patterns, and time decay. It enables
the AI agent to maintain a healthy memory footprint while preserving critical
knowledge.

Key Features:
- Spaced repetition for important memories
- Time-decay based forgetting curves
- Automatic consolidation of frequently-used memories
- Selective pruning based on multi-factor criteria
- Memory refresh scheduling
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json


class ForgetfulnessLevel(Enum):
    """How aggressively should memories be forgotten?"""
    VERY_CONSERVATIVE = 0.1    # Keep 90% of memories
    CONSERVATIVE = 0.3         # Keep 70% of memories
    BALANCED = 0.5             # Keep 50% of memories (default)
    AGGRESSIVE = 0.7           # Keep 30% of memories
    VERY_AGGRESSIVE = 0.9      # Keep 10% of memories


@dataclass
class ForgetfullnessCurve:
    """Defines how quickly a memory is forgotten over time."""
    memory_id: str
    importance_weight: float       # 0-1: How important is this?
    usage_velocity: float          # Accesses per day
    creation_date: datetime
    last_accessed: datetime
    access_history: List[datetime] = field(default_factory=list)
    
    def compute_memory_age_days(self) -> int:
        """How many days old is this memory?"""
        return (datetime.now() - self.creation_date).days
    
    def compute_days_since_last_access(self) -> int:
        """How many days since last access?"""
        return (datetime.now() - self.last_accessed).days
    
    def compute_retention_score(self) -> float:
        """
        Compute how much longer this memory should be retained (0-1).
        
        Factors:
        - Importance (40%): High importance = keep longer
        - Usage velocity (30%): Frequently used = keep longer
        - Recency (20%): Recently used = keep longer
        - Stability (10%): Consistent usage = keep longer
        
        Returns:
            Retention score (0-1). High score = keep memory.
        """
        importance_factor = self.importance_weight
        
        # Usage velocity factor: cap at 10 accesses per day
        usage_factor = min(self.usage_velocity / 10.0, 1.0)
        
        # Recency factor: exponential decay
        days_since_access = self.compute_days_since_last_access()
        if days_since_access <= 7:
            recency_factor = 1.0
        elif days_since_access <= 30:
            recency_factor = 0.8
        elif days_since_access <= 90:
            recency_factor = 0.5
        else:
            recency_factor = max(0.1, 1.0 - (days_since_access - 90) / 365)
        
        # Stability factor: is usage pattern consistent?
        stability_factor = self._compute_stability()
        
        retention = (
            (importance_factor * 0.4) +
            (usage_factor * 0.3) +
            (recency_factor * 0.2) +
            (stability_factor * 0.1)
        )
        
        return min(max(retention, 0.0), 1.0)
    
    def _compute_stability(self) -> float:
        """Compute stability of access pattern (0-1)."""
        if len(self.access_history) < 3:
            return 0.5  # Unknown stability
        
        # Compute interval consistency
        recent_accesses = self.access_history[-10:]  # Last 10 accesses
        if len(recent_accesses) < 2:
            return 0.5
        
        intervals = []
        for i in range(len(recent_accesses) - 1):
            interval = (recent_accesses[i+1] - recent_accesses[i]).days
            intervals.append(interval)
        
        if not intervals:
            return 0.5
        
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval == 0:
            return 1.0  # Very recent, very stable
        
        # Standard deviation of intervals
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        # Lower std_dev = more stable
        stability = max(0.0, 1.0 - (std_dev / (avg_interval + 1)))
        return stability
    
    def should_be_forgotten(self, forgetfulness_level: ForgetfulnessLevel) -> bool:
        """
        Determine if this memory should be forgotten.
        
        Args:
            forgetfulness_level: System's forgetting aggressiveness.
            
        Returns:
            True if memory should be forgotten.
        """
        retention_score = self.compute_retention_score()
        threshold = forgetfulness_level.value
        return retention_score < threshold


@dataclass
class SpacedRepetition:
    """Schedule for reviewing important memories."""
    memory_id: str
    importance: float              # 0-1
    next_review_date: datetime
    review_interval_days: int      # Days until next review
    review_count: int              # How many times has it been reviewed?
    
    def should_review_now(self) -> bool:
        """Is it time to review this memory?"""
        return datetime.now() >= self.next_review_date
    
    def record_review(self):
        """Record that this memory was reviewed."""
        self.review_count += 1
        # Increase interval after each review (up to 1 year)
        self.review_interval_days = min(
            int(self.review_interval_days * 1.5),
            365
        )
        self.next_review_date = (
            datetime.now() + timedelta(days=self.review_interval_days)
        )
    
    def get_review_schedule(self) -> str:
        """Get human-readable review schedule."""
        days_until = (self.next_review_date - datetime.now()).days
        if days_until < 0:
            return "OVERDUE"
        elif days_until == 0:
            return "Today"
        elif days_until == 1:
            return "Tomorrow"
        else:
            return f"In {days_until} days"


class AdaptiveForgetfulnessManager:
    """
    Manages intelligent memory forgetting and retention.
    
    Responsibilities:
    - Schedule spaced repetition for important memories
    - Compute retention scores based on multiple factors
    - Identify memories ready for forgetting
    - Consolidate frequently-used memories
    - Generate forgetting reports
    """
    
    def __init__(self, forgetfulness_level: ForgetfulnessLevel = ForgetfulnessLevel.BALANCED):
        """
        Initialize the forgetting manager.
        
        Args:
            forgetfulness_level: How aggressively to forget.
        """
        self.forgetfulness_level = forgetfulness_level
        self.forgetting_curves: Dict[str, ForgetfullnessCurve] = {}
        self.spaced_repetitions: Dict[str, SpacedRepetition] = {}
        self.forgotten_log: List[Tuple[str, str, datetime]] = []  # (id, reason, time)
        self.consolidation_log: List[Tuple[str, datetime]] = []  # (id, consolidated_time)
    
    def register_memory(
        self,
        memory_id: str,
        importance: float = 0.5,
    ):
        """
        Register a memory for forgetting management.
        
        Args:
            memory_id: Unique memory identifier.
            importance: How important is this memory? (0-1)
        """
        if memory_id not in self.forgetting_curves:
            curve = ForgetfullnessCurve(
                memory_id=memory_id,
                importance_weight=importance,
                usage_velocity=0.0,
                creation_date=datetime.now(),
                last_accessed=datetime.now(),
            )
            self.forgetting_curves[memory_id] = curve
            
            # Schedule spaced repetition for important memories
            if importance > 0.6:
                self._schedule_review(memory_id, importance)
    
    def record_access(self, memory_id: str):
        """
        Record that a memory was accessed.
        
        Args:
            memory_id: The accessed memory.
        """
        if memory_id not in self.forgetting_curves:
            self.register_memory(memory_id)
        
        curve = self.forgetting_curves[memory_id]
        curve.last_accessed = datetime.now()
        curve.access_history.append(datetime.now())
        
        # Update usage velocity (exponential moving average)
        if len(curve.access_history) > 1:
            days_span = (
                curve.access_history[-1] - curve.access_history[0]
            ).days + 1
            accesses = len(curve.access_history)
            velocity = accesses / max(days_span, 1)
            curve.usage_velocity = (curve.usage_velocity * 0.8) + (velocity * 0.2)
    
    def get_forgetting_candidates(self) -> List[Tuple[str, float]]:
        """
        Identify memories that should be forgotten.
        
        Returns:
            List of (memory_id, retention_score) tuples, sorted by retention_score.
        """
        candidates = []
        
        for memory_id, curve in self.forgetting_curves.items():
            retention_score = curve.compute_retention_score()
            
            if curve.should_be_forgotten(self.forgetfulness_level):
                candidates.append((memory_id, retention_score))
        
        # Sort by retention score (ascending)
        candidates.sort(key=lambda x: x[1])
        return candidates
    
    def forget_memory(self, memory_id: str, reason: str = "Low retention score"):
        """
        Remove a memory.
        
        Args:
            memory_id: The memory to forget.
            reason: Why is it being forgotten?
        """
        if memory_id in self.forgetting_curves:
            del self.forgetting_curves[memory_id]
        
        if memory_id in self.spaced_repetitions:
            del self.spaced_repetitions[memory_id]
        
        self.forgotten_log.append((memory_id, reason, datetime.now()))
    
    def get_review_schedule(self) -> List[Tuple[str, str]]:
        """
        Get memories that need review.
        
        Returns:
            List of (memory_id, schedule) tuples.
        """
        schedule = []
        for memory_id, review in self.spaced_repetitions.items():
            if review.should_review_now():
                schedule.append((memory_id, "OVERDUE"))
            else:
                schedule.append((memory_id, review.get_review_schedule()))
        
        return schedule
    
    def perform_review(self, memory_id: str):
        """
        Record that a memory was reviewed.
        
        Args:
            memory_id: The memory that was reviewed.
        """
        if memory_id in self.spaced_repetitions:
            self.spaced_repetitions[memory_id].record_review()
            # Update last accessed
            self.record_access(memory_id)
    
    def consolidate_memory(self, memory_id: str) -> bool:
        """
        Consolidate a frequently-used memory (strengthen it).
        
        Consolidation increases importance and extends retention.
        
        Args:
            memory_id: The memory to consolidate.
            
        Returns:
            True if consolidation succeeded.
        """
        if memory_id not in self.forgetting_curves:
            return False
        
        curve = self.forgetting_curves[memory_id]
        
        # Increase importance if frequently used
        if curve.usage_velocity > 2.0:  # More than 2 accesses per day
            curve.importance_weight = min(1.0, curve.importance_weight + 0.1)
            self.consolidation_log.append((memory_id, datetime.now()))
            
            # Re-schedule review with higher frequency
            if curve.importance_weight > 0.6:
                self._schedule_review(memory_id, curve.importance_weight)
            
            return True
        
        return False
    
    def _schedule_review(self, memory_id: str, importance: float):
        """
        Schedule spaced repetition for a memory.
        
        Args:
            memory_id: The memory to schedule.
            importance: Importance level (0-1).
        """
        # Initial interval based on importance
        initial_interval = max(1, int(30 * (1 - importance)))  # 1-30 days
        
        review = SpacedRepetition(
            memory_id=memory_id,
            importance=importance,
            next_review_date=datetime.now() + timedelta(days=initial_interval),
            review_interval_days=initial_interval,
            review_count=0,
        )
        
        self.spaced_repetitions[memory_id] = review
    
    def prune_memories(self) -> List[str]:
        """
        Automatically forget low-retention memories.
        
        Returns:
            List of forgotten memory IDs.
        """
        candidates = self.get_forgetting_candidates()
        forgotten = []
        
        for memory_id, retention_score in candidates:
            reason = f"Low retention score: {retention_score:.2f}"
            self.forget_memory(memory_id, reason)
            forgotten.append(memory_id)
        
        return forgotten
    
    def consolidate_high_usage_memories(self) -> List[str]:
        """
        Consolidate memories with high usage velocity.
        
        Returns:
            List of consolidated memory IDs.
        """
        consolidated = []
        
        for memory_id in self.forgetting_curves.keys():
            if self.consolidate_memory(memory_id):
                consolidated.append(memory_id)
        
        return consolidated
    
    def get_memory_health(self, memory_id: str) -> Dict:
        """
        Get health report for a memory.
        
        Args:
            memory_id: The memory to analyze.
            
        Returns:
            Dictionary with health information.
        """
        if memory_id not in self.forgetting_curves:
            return {"error": f"Memory {memory_id} not found"}
        
        curve = self.forgetting_curves[memory_id]
        
        return {
            "memory_id": memory_id,
            "importance": curve.importance_weight,
            "retention_score": curve.compute_retention_score(),
            "usage_velocity": curve.usage_velocity,
            "age_days": curve.compute_memory_age_days(),
            "days_since_access": curve.compute_days_since_last_access(),
            "access_count": len(curve.access_history),
            "stability": curve._compute_stability(),
            "will_be_forgotten": curve.should_be_forgotten(self.forgetfulness_level),
            "review_status": (
                self.spaced_repetitions[memory_id].get_review_schedule()
                if memory_id in self.spaced_repetitions else "Not scheduled"
            ),
        }
    
    def get_statistics(self) -> Dict:
        """Get overall forgetting statistics."""
        if not self.forgetting_curves:
            return {
                "total_memories": 0,
                "avg_retention": 0.0,
                "memories_scheduled_for_review": 0,
                "total_forgotten": len(self.forgotten_log),
                "total_consolidated": len(self.consolidation_log),
            }
        
        curves = self.forgetting_curves.values()
        retention_scores = [c.compute_retention_score() for c in curves]
        
        review_count = sum(
            1 for mem_id in self.spaced_repetitions
            if self.spaced_repetitions[mem_id].should_review_now()
        )
        
        return {
            "total_memories": len(self.forgetting_curves),
            "avg_retention_score": sum(retention_scores) / len(retention_scores),
            "high_retention": sum(1 for r in retention_scores if r > 0.8),
            "medium_retention": sum(1 for r in retention_scores if 0.4 < r <= 0.8),
            "low_retention": sum(1 for r in retention_scores if r <= 0.4),
            "memories_scheduled_for_review": len(self.spaced_repetitions),
            "memories_overdue_for_review": review_count,
            "total_forgotten": len(self.forgotten_log),
            "total_consolidated": len(self.consolidation_log),
        }
    
    def export_report(self, filepath: str):
        """
        Export forgetting statistics to JSON.
        
        Args:
            filepath: Output file path.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "forgetfulness_level": self.forgetfulness_level.name,
            "statistics": self.get_statistics(),
            "review_schedule": dict(self.get_review_schedule()),
            "forgotten_log": [
                {
                    "memory_id": f[0],
                    "reason": f[1],
                    "timestamp": f[2].isoformat(),
                }
                for f in self.forgotten_log[-50:]  # Last 50
            ],
            "consolidation_log": [
                {
                    "memory_id": c[0],
                    "timestamp": c[1].isoformat(),
                }
                for c in self.consolidation_log[-50:]  # Last 50
            ],
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
