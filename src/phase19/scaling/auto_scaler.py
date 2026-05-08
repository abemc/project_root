"""Auto Scaler - dynamically scales resources based on load."""

import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ScalingPolicy(Enum):
    """Scaling policies."""
    CPU_BASED = "cpu_based"
    MEMORY_BASED = "memory_based"
    REQUEST_RATE_BASED = "request_rate_based"
    LATENCY_BASED = "latency_based"
    SCHEDULE_BASED = "schedule_based"


class ScalingDirection(Enum):
    """Scaling direction."""
    SCALE_OUT = "scale_out"   # Add instances
    SCALE_IN = "scale_in"     # Remove instances
    NO_CHANGE = "no_change"


@dataclass
class ScalingRule:
    """Defines a scaling rule."""
    rule_id: str
    policy: ScalingPolicy
    scale_out_threshold: float  # Metric value to trigger scale out
    scale_in_threshold: float   # Metric value to trigger scale in
    scale_out_increment: int = 1  # Instances to add
    scale_in_decrement: int = 1   # Instances to remove
    cooldown_seconds: int = 60    # Seconds between scaling actions
    min_instances: int = 1
    max_instances: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "policy": self.policy.value,
            "scale_out_threshold": self.scale_out_threshold,
            "scale_in_threshold": self.scale_in_threshold,
            "scale_out_increment": self.scale_out_increment,
            "scale_in_decrement": self.scale_in_decrement,
            "cooldown_seconds": self.cooldown_seconds,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances
        }


@dataclass
class ScalingEvent:
    """Records a scaling action."""
    event_id: str
    direction: ScalingDirection
    instances_before: int
    instances_after: int
    rule_id: str
    trigger_metric: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "direction": self.direction.value,
            "instances_before": self.instances_before,
            "instances_after": self.instances_after,
            "rule_id": self.rule_id,
            "trigger_metric": self.trigger_metric,
            "timestamp": self.timestamp,
            "reason": self.reason
        }


class AutoScaler:
    """Dynamically scales resources based on metrics.
    
    Features:
    - Multiple scaling policies
    - Cooldown periods to prevent thrashing
    - Min/max instance bounds
    - Scale out/in history
    - Custom scaling callbacks
    """

    def __init__(
        self,
        min_instances: int = 1,
        max_instances: int = 10,
        initial_instances: int = 1
    ):
        """Initialize auto scaler.
        
        Args:
            min_instances: Minimum number of instances
            max_instances: Maximum number of instances
            initial_instances: Starting number of instances
        """
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.current_instances = initial_instances
        self.rules: Dict[str, ScalingRule] = {}
        self.events: List[ScalingEvent] = []
        self._last_scaling: Dict[str, float] = {}  # rule_id -> timestamp
        self._lock = threading.RLock()
        self._scale_out_callback: Optional[Callable[[int], None]] = None
        self._scale_in_callback: Optional[Callable[[int], None]] = None
        self._event_counter = 0

    def add_rule(self, rule: ScalingRule) -> None:
        """Add a scaling rule.
        
        Args:
            rule: Scaling rule to add
        """
        with self._lock:
            self.rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a scaling rule.
        
        Args:
            rule_id: Rule to remove
            
        Returns:
            True if rule was removed
        """
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                return True
            return False

    def set_scale_out_callback(self, callback: Callable[[int], None]) -> None:
        """Set callback for scale out events.
        
        Args:
            callback: Called with new instance count on scale out
        """
        self._scale_out_callback = callback

    def set_scale_in_callback(self, callback: Callable[[int], None]) -> None:
        """Set callback for scale in events.
        
        Args:
            callback: Called with new instance count on scale in
        """
        self._scale_in_callback = callback

    def evaluate_metrics(self, metrics: Dict[str, float]) -> List[ScalingEvent]:
        """Evaluate metrics against scaling rules.
        
        Args:
            metrics: Dict mapping metric names to values
            
        Returns:
            List of scaling events that occurred
        """
        with self._lock:
            triggered_events = []

            for rule_id, rule in self.rules.items():
                if self._is_in_cooldown(rule_id, rule.cooldown_seconds):
                    continue

                metric_value = self._get_metric_for_policy(metrics, rule.policy)
                if metric_value is None:
                    continue

                direction = self._evaluate_rule(rule, metric_value)
                if direction == ScalingDirection.NO_CHANGE:
                    continue

                event = self._execute_scaling(rule, direction, metric_value)
                if event:
                    triggered_events.append(event)
                    self._last_scaling[rule_id] = time.time()

            return triggered_events

    def scale_out(self, count: int = 1, reason: str = "Manual scale out") -> ScalingEvent:
        """Manually scale out.
        
        Args:
            count: Instances to add
            reason: Scale out reason
            
        Returns:
            ScalingEvent
        """
        with self._lock:
            before = self.current_instances
            new_count = min(self.current_instances + count, self.max_instances)
            self.current_instances = new_count

            self._event_counter += 1
            event = ScalingEvent(
                event_id=f"evt_{self._event_counter}",
                direction=ScalingDirection.SCALE_OUT,
                instances_before=before,
                instances_after=new_count,
                rule_id="manual",
                trigger_metric=0.0,
                reason=reason
            )
            self.events.append(event)

            if self._scale_out_callback and new_count > before:
                self._scale_out_callback(new_count)

            return event

    def scale_in(self, count: int = 1, reason: str = "Manual scale in") -> ScalingEvent:
        """Manually scale in.
        
        Args:
            count: Instances to remove
            reason: Scale in reason
            
        Returns:
            ScalingEvent
        """
        with self._lock:
            before = self.current_instances
            new_count = max(self.current_instances - count, self.min_instances)
            self.current_instances = new_count

            self._event_counter += 1
            event = ScalingEvent(
                event_id=f"evt_{self._event_counter}",
                direction=ScalingDirection.SCALE_IN,
                instances_before=before,
                instances_after=new_count,
                rule_id="manual",
                trigger_metric=0.0,
                reason=reason
            )
            self.events.append(event)

            if self._scale_in_callback and new_count < before:
                self._scale_in_callback(new_count)

            return event

    def get_scaling_history(self) -> List[ScalingEvent]:
        """Get scaling event history.
        
        Returns:
            List of scaling events
        """
        return self.events.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get auto scaler statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            scale_outs = sum(1 for e in self.events if e.direction == ScalingDirection.SCALE_OUT)
            scale_ins = sum(1 for e in self.events if e.direction == ScalingDirection.SCALE_IN)

            return {
                "current_instances": self.current_instances,
                "min_instances": self.min_instances,
                "max_instances": self.max_instances,
                "active_rules": len(self.rules),
                "total_events": len(self.events),
                "scale_out_events": scale_outs,
                "scale_in_events": scale_ins,
                "utilization": self.current_instances / self.max_instances
            }

    def _is_in_cooldown(self, rule_id: str, cooldown_seconds: int) -> bool:
        """Check if rule is in cooldown period."""
        if rule_id not in self._last_scaling:
            return False
        elapsed = time.time() - self._last_scaling[rule_id]
        return elapsed < cooldown_seconds

    def _get_metric_for_policy(
        self,
        metrics: Dict[str, float],
        policy: ScalingPolicy
    ) -> Optional[float]:
        """Get relevant metric value for policy."""
        mapping = {
            ScalingPolicy.CPU_BASED: "cpu_percent",
            ScalingPolicy.MEMORY_BASED: "memory_percent",
            ScalingPolicy.REQUEST_RATE_BASED: "request_rate",
            ScalingPolicy.LATENCY_BASED: "latency_ms"
        }
        metric_name = mapping.get(policy)
        return metrics.get(metric_name)

    def _evaluate_rule(
        self,
        rule: ScalingRule,
        metric_value: float
    ) -> ScalingDirection:
        """Evaluate if rule should trigger scaling."""
        if metric_value >= rule.scale_out_threshold:
            if self.current_instances < rule.max_instances:
                return ScalingDirection.SCALE_OUT
        elif metric_value <= rule.scale_in_threshold:
            if self.current_instances > rule.min_instances:
                return ScalingDirection.SCALE_IN
        return ScalingDirection.NO_CHANGE

    def _execute_scaling(
        self,
        rule: ScalingRule,
        direction: ScalingDirection,
        metric_value: float
    ) -> Optional[ScalingEvent]:
        """Execute scaling action."""
        before = self.current_instances

        if direction == ScalingDirection.SCALE_OUT:
            self.current_instances = min(
                self.current_instances + rule.scale_out_increment,
                rule.max_instances
            )
        elif direction == ScalingDirection.SCALE_IN:
            self.current_instances = max(
                self.current_instances - rule.scale_in_decrement,
                rule.min_instances
            )

        if self.current_instances == before:
            return None

        self._event_counter += 1
        event = ScalingEvent(
            event_id=f"evt_{self._event_counter}",
            direction=direction,
            instances_before=before,
            instances_after=self.current_instances,
            rule_id=rule.rule_id,
            trigger_metric=metric_value,
            reason=f"Rule {rule.rule_id}: metric={metric_value:.2f}"
        )
        self.events.append(event)

        if direction == ScalingDirection.SCALE_OUT and self._scale_out_callback:
            self._scale_out_callback(self.current_instances)
        elif direction == ScalingDirection.SCALE_IN and self._scale_in_callback:
            self._scale_in_callback(self.current_instances)

        return event
