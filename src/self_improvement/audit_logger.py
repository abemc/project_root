"""
Phase 4: Audit Logger
=====================

Complete audit logging system for tracking all autonomous improvements:
- Feedback analysis logs
- Prompt optimization logs
- Training progress logs
- Rollback events
- A/B testing results
- Performance metrics

Features:
  - JSON-based persistent storage
  - SQL-like querying
  - Time-series analysis
  - Alert conditions
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Audit event types"""
    FEEDBACK_COLLECTED = "feedback_collected"
    PROMPT_OPTIMIZED = "prompt_optimized"
    TRAINING_COMPLETED = "training_completed"
    METRIC_VERIFIED = "metric_verified"
    ROLLBACK_TRIGGERED = "rollback_triggered"
    ROLLBACK_EXECUTED = "rollback_executed"
    AB_TEST_STARTED = "ab_test_started"
    AB_TEST_COMPLETED = "ab_test_completed"
    ALERT_TRIGGERED = "alert_triggered"
    SYSTEM_INITIALIZED = "system_initialized"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class AuditEvent:
    """Single audit log event"""
    event_id: str
    event_type: EventType
    timestamp: str
    component: str  # Which phase/module triggered this
    severity: AlertSeverity
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)
    metrics_snapshot: Optional[Dict[str, float]] = None
    user: str = "autonomous_system"

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        result = asdict(self)
        result["event_type"] = self.event_type.value
        result["severity"] = self.severity.value
        return result

    @classmethod
    def from_dict(cls, data: Dict):
        """Create from dict"""
        data = data.copy()
        data["event_type"] = EventType(data["event_type"])
        data["severity"] = AlertSeverity(data["severity"])
        return cls(**data)


@dataclass
class AlertRule:
    """Alert rule definition"""
    rule_id: str
    name: str
    trigger_condition: str  # e.g., "rating_drop > 0.2"
    severity: AlertSeverity
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=list)


class AuditLogger:
    """Complete audit logging system"""

    def __init__(self, log_dir: str = None):
        """
        Args:
            log_dir: Directory for audit logs (default: logs/audit)
        """
        if log_dir is None:
            log_dir = Path("logs/audit")
        else:
            log_dir = Path(log_dir)

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.events_file = self.log_dir / "events.jsonl"
        self.alerts_file = self.log_dir / "alerts.jsonl"
        self.summary_file = self.log_dir / "summary.json"

        # In-memory event storage
        self.events: List[AuditEvent] = []
        self.active_alerts: List[AuditEvent] = []
        self.alert_rules: Dict[str, AlertRule] = {}

        # Load existing data
        self._load_events()
        self._initialize_alert_rules()

        logger.info(f"AuditLogger initialized (log_dir={self.log_dir})")

    def log_event(
        self,
        event_type: EventType,
        component: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        detail: Optional[Dict] = None,
        metrics_snapshot: Optional[Dict[str, float]] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            component: Which component triggered this (e.g., "phase_1", "ab_testing")
            message: Human-readable message
            severity: Severity level
            detail: Additional details
            metrics_snapshot: Snapshot of current metrics

        Returns:
            Created AuditEvent
        """
        event_id = self._generate_event_id()
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            component=component,
            severity=severity,
            message=message,
            detail=detail or {},
            metrics_snapshot=metrics_snapshot,
        )

        self.events.append(event)
        self._persist_event(event)

        if severity == AlertSeverity.CRITICAL:
            self.active_alerts.append(event)
            self._persist_alert(event)
            logger.warning(f"🚨 CRITICAL ALERT: {message}")

        logger.info(f"[{event_type.value}] {message}")
        return event

    def get_events(
        self,
        component: Optional[str] = None,
        event_type: Optional[EventType] = None,
        time_range: Optional[tuple] = None,
        limit: int = None,
    ) -> List[AuditEvent]:
        """
        Query events with filters.

        Args:
            component: Filter by component
            event_type: Filter by event type
            time_range: (start_time, end_time) in ISO format
            limit: Max number of results

        Returns:
            Filtered list of events
        """
        results = self.events

        if component:
            results = [e for e in results if e.component == component]

        if event_type:
            results = [e for e in results if e.event_type == event_type]

        if time_range:
            start, end = time_range
            results = [
                e for e in results
                if start <= e.timestamp <= end
            ]

        # Sort by most recent first
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)

        if limit:
            results = results[:limit]

        return results

    def get_phase_summary(self, phase: str) -> Dict[str, Any]:
        """
        Get summary statistics for a phase.

        Args:
            phase: Phase identifier (e.g., "phase_1", "phase_2", "phase_3")

        Returns:
            Summary dict with counts and stats
        """
        phase_events = self.get_events(component=phase)

        if not phase_events:
            return {
                "phase": phase,
                "total_events": 0,
                "event_breakdown": {},
                "recent_events": [],
            }

        breakdown = {}
        for event in phase_events:
            event_type_str = event.event_type.value
            breakdown[event_type_str] = breakdown.get(event_type_str, 0) + 1

        return {
            "phase": phase,
            "total_events": len(phase_events),
            "event_breakdown": breakdown,
            "recent_events": [
                {
                    "timestamp": e.timestamp,
                    "type": e.event_type.value,
                    "message": e.message,
                }
                for e in phase_events[:5]
            ],
            "last_event_time": phase_events[0].timestamp if phase_events else None,
        }

    def get_performance_timeline(
        self, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics timeline for last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of timeline entries with metrics
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        recent_events = self.get_events(time_range=(cutoff, datetime.now().isoformat()))

        timeline = []
        metric_snapshots = [e.metrics_snapshot for e in recent_events if e.metrics_snapshot]

        for i, metrics in enumerate(metric_snapshots):
            if metrics:
                timeline.append({
                    "index": i,
                    "timestamp": recent_events[i].timestamp if i < len(recent_events) else None,
                    "metrics": metrics,
                })

        return timeline

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect performance anomalies from recent events.

        Returns:
            List of detected anomalies
        """
        anomalies = []
        recent_events = self.get_events(limit=50)

        # Check for rating drops
        ratings = []
        for event in recent_events:
            if event.metrics_snapshot and "average_rating" in event.metrics_snapshot:
                ratings.append(event.metrics_snapshot["average_rating"])

        if len(ratings) >= 2:
            for i in range(1, len(ratings)):
                drop = ratings[i - 1] - ratings[i]
                if drop > 0.2:  # More than 20% drop
                    anomalies.append({
                        "type": "rating_drop",
                        "magnitude": drop,
                        "timestamp": recent_events[i].timestamp,
                        "severity": "high" if drop > 0.3 else "medium",
                    })

        # Check for rollback frequency
        rollback_events = self.get_events(event_type=EventType.ROLLBACK_EXECUTED, limit=10)
        if len(rollback_events) >= 3:
            anomalies.append({
                "type": "frequent_rollbacks",
                "count": len(rollback_events),
                "timestamp": datetime.now().isoformat(),
                "severity": "medium",
                "message": f"System rolled back {len(rollback_events)} times in recent history",
            })

        return anomalies

    def log_ab_test_result(
        self,
        test_id: str,
        best_candidate: str,
        recommendation: str,
        metrics: Dict[str, float],
    ) -> AuditEvent:
        """Log A/B testing completion"""
        return self.log_event(
            event_type=EventType.AB_TEST_COMPLETED,
            component="phase_3",
            message=f"A/B test {test_id}: {recommendation} ({best_candidate})",
            severity=AlertSeverity.INFO if recommendation == "ADOPT" else AlertSeverity.WARNING,
            detail={
                "test_id": test_id,
                "best_candidate": best_candidate,
                "recommendation": recommendation,
            },
            metrics_snapshot=metrics,
        )

    def log_rollback_event(
        self,
        reason: str,
        from_state: str,
        to_state: str,
    ) -> AuditEvent:
        """Log rollback execution"""
        return self.log_event(
            event_type=EventType.ROLLBACK_EXECUTED,
            component="phase_2",
            message=f"Rollback: {reason}",
            severity=AlertSeverity.CRITICAL,
            detail={
                "reason": reason,
                "from_state": from_state,
                "to_state": to_state,
            },
        )

    def get_summary_report(self) -> Dict[str, Any]:
        """Generate complete system summary report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "total_events": len(self.events),
            "phase_summaries": {
                "phase_1": self.get_phase_summary("phase_1"),
                "phase_2": self.get_phase_summary("phase_2"),
                "phase_3": self.get_phase_summary("phase_3"),
            },
            "active_alerts": len(self.active_alerts),
            "recent_anomalies": self.detect_anomalies(),
            "events_by_severity": {
                "INFO": len([e for e in self.events if e.severity == AlertSeverity.INFO]),
                "WARNING": len([e for e in self.events if e.severity == AlertSeverity.WARNING]),
                "CRITICAL": len([e for e in self.events if e.severity == AlertSeverity.CRITICAL]),
            },
        }

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        timestamp = datetime.now().isoformat()
        hash_input = f"{timestamp}{len(self.events)}".encode()
        return hashlib.md5(hash_input).hexdigest()[:12]

    def _persist_event(self, event: AuditEvent):
        """Write event to persistent storage"""
        with open(self.events_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def _persist_alert(self, alert: AuditEvent):
        """Write alert to persistent storage"""
        with open(self.alerts_file, "a") as f:
            f.write(json.dumps(alert.to_dict()) + "\n")

    def _load_events(self):
        """Load events from persistent storage"""
        if not self.events_file.exists():
            return

        with open(self.events_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        event = AuditEvent.from_dict(data)
                        self.events.append(event)
                    except Exception as e:
                        logger.warning(f"Failed to load event: {e}")

        logger.info(f"Loaded {len(self.events)} events from storage")

    def _initialize_alert_rules(self):
        """Initialize default alert rules"""
        self.alert_rules = {
            "low_rating": AlertRule(
                rule_id="low_rating",
                name="Low User Rating",
                trigger_condition="average_rating < 0.6",
                severity=AlertSeverity.WARNING,
                enabled=True,
                notification_channels=["log", "dashboard"],
            ),
            "rating_drop": AlertRule(
                rule_id="rating_drop",
                name="Rating Drop Detected",
                trigger_condition="rating_drop > 0.2",
                severity=AlertSeverity.WARNING,
                enabled=True,
                notification_channels=["log", "dashboard"],
            ),
            "error_rate_high": AlertRule(
                rule_id="error_rate_high",
                name="High Error Rate",
                trigger_condition="error_rate > 0.1",
                severity=AlertSeverity.CRITICAL,
                enabled=True,
                notification_channels=["log", "dashboard", "alert"],
            ),
        }
