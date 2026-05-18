"""
Transfer Learning: Share knowledge across different tasks and domains.

This module implements transfer learning mechanisms that allow the AI agent to
apply learnings from one task domain to another, significantly reducing the
time needed to master new tasks.

Key Features:
- Task family classification and similarity computation
- Knowledge transfer between related tasks
- Cross-task pattern application
- Domain adaptation techniques
- Transfer success tracking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
import json
import hashlib


class TaskFamily(Enum):
    """Categories of tasks that can share knowledge."""
    FILE_OPERATIONS = "file_ops"        # Read, write, delete files
    DATA_ANALYSIS = "data_analysis"     # Process, analyze data
    TEXT_PROCESSING = "text_proc"       # Parse, transform text
    SYSTEM_ADMIN = "sys_admin"          # Config, monitoring
    API_INTEGRATION = "api_integration" # External service calls
    DATABASE_OPS = "database_ops"       # SQL, queries
    VISUALIZATION = "visualization"    # Charts, graphs
    MACHINE_LEARNING = "ml"             # Model training, inference


@dataclass
class TaskCharacteristics:
    """Properties of a task that enable transfer."""
    task_id: str
    task_family: TaskFamily
    input_type: str                     # csv, json, images, etc.
    output_type: str                    # results format
    complexity_score: float             # 0-1: Task difficulty
    processing_time_ms: float           # Average execution time
    success_rate: float                 # 0-1: Historical success
    tools_required: List[str]           # Tools needed
    parameters: Dict[str, Any]          # Config parameters
    
    def compute_similarity(self, other: "TaskCharacteristics") -> float:
        """
        Compute similarity to another task (0-1).
        
        Factors:
        - Same family (40%)
        - Same input type (20%)
        - Similar complexity (20%)
        - Same tools (20%)
        
        Args:
            other: Other task to compare.
            
        Returns:
            Similarity score (0-1).
        """
        family_match = 1.0 if self.task_family == other.task_family else 0.0
        input_match = 1.0 if self.input_type == other.input_type else 0.0
        
        # Complexity similarity (1 if within 0.2 range)
        complexity_diff = abs(self.complexity_score - other.complexity_score)
        complexity_match = max(0.0, 1.0 - (complexity_diff / 0.2))
        
        # Tools overlap
        tools_self = set(self.tools_required)
        tools_other = set(other.tools_required)
        if tools_self and tools_other:
            tools_overlap = len(tools_self & tools_other) / len(tools_self | tools_other)
        else:
            tools_overlap = 0.0
        
        similarity = (
            (family_match * 0.4) +
            (input_match * 0.2) +
            (complexity_match * 0.2) +
            (tools_overlap * 0.2)
        )
        
        return min(max(similarity, 0.0), 1.0)


@dataclass
class TransferableKnowledge:
    """Knowledge that can be transferred between tasks."""
    knowledge_id: str
    source_task_id: str                 # Where did this come from?
    knowledge_type: str                 # parameter_set | error_recovery | optimization
    content: Dict[str, Any]             # The actual knowledge
    applicability_score: float          # 0-1: How general is this?
    transfer_success_count: int         # Times this was successfully applied
    transfer_failure_count: int         # Times this failed
    
    def success_rate(self) -> float:
        """Compute success rate of this transfer (0-1)."""
        total = self.transfer_success_count + self.transfer_failure_count
        if total == 0:
            return 0.5
        return self.transfer_success_count / total
    
    def credibility(self) -> float:
        """
        Compute credibility of this transfer knowledge (0-1).
        
        Factors:
        - Applicability (50%)
        - Success rate (50%)
        
        Returns:
            Credibility score (0-1).
        """
        return (
            (self.applicability_score * 0.5) +
            (self.success_rate() * 0.5)
        )


@dataclass
class TransferAttempt:
    """Record of attempting to transfer knowledge."""
    attempt_id: str
    source_task_id: str
    target_task_id: str
    knowledge_id: str
    adaptation_made: bool               # Did we adapt the knowledge?
    success: bool                       # Did the transfer succeed?
    success_score: float                # 0-1: How successful?
    timestamp: datetime = field(default_factory=datetime.now)


class TransferLearningManager:
    """
    Manages transfer of knowledge between tasks.
    
    Responsibilities:
    - Track task families and characteristics
    - Identify transferable knowledge
    - Adapt knowledge for new contexts
    - Record transfer successes and failures
    - Recommend applicable knowledge for new tasks
    """
    
    def __init__(self):
        """Initialize transfer learning manager."""
        self.task_registry: Dict[str, TaskCharacteristics] = {}
        self.transferable_knowledge: Dict[str, TransferableKnowledge] = {}
        self.transfer_graph: Dict[str, List[str]] = {}  # task_id → [transferable_knowledge_ids]
        self.transfer_history: List[TransferAttempt] = []
        self.family_hierarchy: Dict[TaskFamily, List[str]] = {}  # family → [task_ids]
    
    def register_task(
        self,
        task_id: str,
        task_family: TaskFamily,
        input_type: str,
        output_type: str,
        complexity_score: float,
        processing_time_ms: float,
        success_rate: float,
        tools_required: List[str],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> TaskCharacteristics:
        """
        Register a task for transfer learning.
        
        Args:
            task_id: Unique task identifier.
            task_family: Category of task.
            input_type: Input data type.
            output_type: Output data type.
            complexity_score: Task difficulty (0-1).
            processing_time_ms: Execution time.
            success_rate: Historical success (0-1).
            tools_required: Tools needed.
            parameters: Optional parameters.
            
        Returns:
            The registered TaskCharacteristics.
        """
        characteristics = TaskCharacteristics(
            task_id=task_id,
            task_family=task_family,
            input_type=input_type,
            output_type=output_type,
            complexity_score=complexity_score,
            processing_time_ms=processing_time_ms,
            success_rate=success_rate,
            tools_required=tools_required,
            parameters=parameters or {},
        )
        
        self.task_registry[task_id] = characteristics
        
        # Update family hierarchy
        if task_family not in self.family_hierarchy:
            self.family_hierarchy[task_family] = []
        self.family_hierarchy[task_family].append(task_id)
        
        return characteristics
    
    def extract_knowledge(
        self,
        task_id: str,
        knowledge_type: str,
        content: Dict[str, Any],
        applicability_score: float = 0.7,
    ) -> TransferableKnowledge:
        """
        Extract knowledge from a completed task.
        
        Args:
            task_id: Task the knowledge comes from.
            knowledge_type: Type of knowledge.
            content: The knowledge content.
            applicability_score: How general is this knowledge?
            
        Returns:
            The extracted TransferableKnowledge.
        """
        knowledge_id = hashlib.md5(
            f"{task_id}{knowledge_type}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        knowledge = TransferableKnowledge(
            knowledge_id=knowledge_id,
            source_task_id=task_id,
            knowledge_type=knowledge_type,
            content=content,
            applicability_score=applicability_score,
            transfer_success_count=0,
            transfer_failure_count=0,
        )
        
        self.transferable_knowledge[knowledge_id] = knowledge
        
        # Index it in the graph
        if task_id not in self.transfer_graph:
            self.transfer_graph[task_id] = []
        self.transfer_graph[task_id].append(knowledge_id)
        
        return knowledge
    
    def find_similar_tasks(
        self,
        task_id: str,
        min_similarity: float = 0.6,
    ) -> List[Tuple[str, float]]:
        """
        Find tasks similar to the given task.
        
        Args:
            task_id: Task to find similarities for.
            min_similarity: Minimum similarity threshold.
            
        Returns:
            List of (similar_task_id, similarity_score) tuples.
        """
        if task_id not in self.task_registry:
            return []
        
        source_task = self.task_registry[task_id]
        similar = []
        
        for other_id, other_task in self.task_registry.items():
            if other_id == task_id:
                continue
            
            similarity = source_task.compute_similarity(other_task)
            if similarity >= min_similarity:
                similar.append((other_id, similarity))
        
        # Sort by similarity (descending)
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar
    
    def recommend_knowledge_transfer(
        self,
        target_task_id: str,
        min_credibility: float = 0.6,
        top_k: int = 5,
    ) -> List[Tuple[str, TransferableKnowledge, float]]:
        """
        Recommend transferable knowledge for a target task.
        
        Args:
            target_task_id: The task needing knowledge.
            min_credibility: Minimum credibility threshold.
            top_k: Number of recommendations.
            
        Returns:
            List of (knowledge_id, knowledge, relevance_score) tuples.
        """
        if target_task_id not in self.task_registry:
            return []
        
        target_task = self.task_registry[target_task_id]
        recommendations = []
        
        for knowledge_id, knowledge in self.transferable_knowledge.items():
            source_task_id = knowledge.source_task_id
            
            # Check credibility
            if knowledge.credibility() < min_credibility:
                continue
            
            # Check source task similarity
            if source_task_id not in self.task_registry:
                continue
            
            source_task = self.task_registry[source_task_id]
            similarity = source_task.compute_similarity(target_task)
            
            # Only recommend if reasonably similar
            if similarity > 0.5:
                relevance = (similarity * 0.6) + (knowledge.credibility() * 0.4)
                recommendations.append((knowledge_id, knowledge, relevance))
        
        # Sort by relevance (descending)
        recommendations.sort(key=lambda x: x[2], reverse=True)
        return recommendations[:top_k]
    
    def attempt_transfer(
        self,
        source_task_id: str,
        target_task_id: str,
        knowledge_id: str,
        adapt: bool = True,
    ) -> Tuple[bool, TransferAttempt]:
        """
        Attempt to transfer knowledge from source to target task.
        
        Args:
            source_task_id: Source task ID.
            target_task_id: Target task ID.
            knowledge_id: Knowledge to transfer.
            adapt: Should we adapt the knowledge?
            
        Returns:
            (success, attempt_record)
        """
        if knowledge_id not in self.transferable_knowledge:
            attempt = TransferAttempt(
                attempt_id=hashlib.md5(f"{source_task_id}{target_task_id}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
                source_task_id=source_task_id,
                target_task_id=target_task_id,
                knowledge_id=knowledge_id,
                adaptation_made=False,
                success=False,
                success_score=0.0,
            )
            self.transfer_history.append(attempt)
            return (False, attempt)
        
        knowledge = self.transferable_knowledge[knowledge_id]
        
        # Compute adaptation needed
        if source_task_id in self.task_registry and target_task_id in self.task_registry:
            source = self.task_registry[source_task_id]
            target = self.task_registry[target_task_id]
            similarity = source.compute_similarity(target)
            
            # Success likelihood based on similarity
            success_likelihood = similarity * knowledge.credibility()
        else:
            success_likelihood = knowledge.credibility()
        
        # Simulate transfer
        success = success_likelihood > 0.5
        success_score = success_likelihood
        
        attempt = TransferAttempt(
            attempt_id=hashlib.md5(
                f"{source_task_id}{target_task_id}{knowledge_id}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            knowledge_id=knowledge_id,
            adaptation_made=adapt and not (similarity > 0.9) if source_task_id in self.task_registry and target_task_id in self.task_registry else adapt,
            success=success,
            success_score=success_score,
        )
        
        self.transfer_history.append(attempt)
        
        # Update knowledge statistics
        if success:
            knowledge.transfer_success_count += 1
        else:
            knowledge.transfer_failure_count += 1
        
        return (success, attempt)
    
    def get_transfer_statistics(self) -> Dict:
        """Get overall transfer learning statistics."""
        if not self.transfer_history:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "avg_success_score": 0.0,
                "knowledge_pieces": len(self.transferable_knowledge),
                "tasks_registered": len(self.task_registry),
            }
        
        attempts = self.transfer_history
        successes = sum(1 for a in attempts if a.success)
        success_scores = [a.success_score for a in attempts]
        
        return {
            "total_attempts": len(attempts),
            "success_rate": successes / len(attempts),
            "avg_success_score": sum(success_scores) / len(success_scores),
            "adaptations_made": sum(1 for a in attempts if a.adaptation_made),
            "knowledge_pieces": len(self.transferable_knowledge),
            "tasks_registered": len(self.task_registry),
            "task_families": len(self.family_hierarchy),
        }
    
    def get_knowledge_impact(self, knowledge_id: str) -> Dict:
        """
        Analyze impact of a piece of knowledge.
        
        Args:
            knowledge_id: Knowledge to analyze.
            
        Returns:
            Impact statistics.
        """
        if knowledge_id not in self.transferable_knowledge:
            return {"error": "Knowledge not found"}
        
        knowledge = self.transferable_knowledge[knowledge_id]
        
        # Find all transfer attempts
        attempts = [a for a in self.transfer_history if a.knowledge_id == knowledge_id]
        
        if not attempts:
            return {
                "knowledge_id": knowledge_id,
                "source_task": knowledge.source_task_id,
                "type": knowledge.knowledge_type,
                "credibility": knowledge.credibility(),
                "transfers_attempted": 0,
                "success_rate": 0.0,
                "avg_impact": 0.0,
            }
        
        successes = sum(1 for a in attempts if a.success)
        avg_impact = sum(a.success_score for a in attempts) / len(attempts)
        
        return {
            "knowledge_id": knowledge_id,
            "source_task": knowledge.source_task_id,
            "type": knowledge.knowledge_type,
            "credibility": knowledge.credibility(),
            "transfers_attempted": len(attempts),
            "success_rate": successes / len(attempts),
            "avg_impact": avg_impact,
            "target_tasks": len(set(a.target_task_id for a in attempts)),
        }
    
    def export_transfer_report(self, filepath: str):
        """
        Export transfer learning analysis to JSON.
        
        Args:
            filepath: Output file path.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.get_transfer_statistics(),
            "task_families": {
                family.name: len(tasks)
                for family, tasks in self.family_hierarchy.items()
            },
            "knowledge_pieces": {
                kid: {
                    "source_task": k.source_task_id,
                    "type": k.knowledge_type,
                    "credibility": k.credibility(),
                    "transfers": k.transfer_success_count + k.transfer_failure_count,
                    "success_rate": k.success_rate(),
                }
                for kid, k in self.transferable_knowledge.items()
            },
            "recent_transfers": [
                {
                    "source_task": a.source_task_id,
                    "target_task": a.target_task_id,
                    "success": a.success,
                    "score": a.success_score,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.transfer_history[-50:]  # Last 50
            ],
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
