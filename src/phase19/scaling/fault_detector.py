"""Fault Detector - detects and recovers from system failures."""

import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque


class FaultType(Enum):
    """Types of faults."""
    TIMEOUT = "timeout"
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CASCADING_FAILURE = "cascading_failure"


class FaultSeverity(Enum):
    """Fault severity levels."""
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FaultEvent:
    """Represents a detected fault."""
    fault_id: str
    fault_type: FaultType
    severity: FaultSeverity
    service_id: str
    metric_value: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved: bool = False
    resolved_at: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fault_id": self.fault_id,
            "fault_type": self.fault_type.value,
            "severity": self.severity.value,
            "service_id": self.service_id,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "details": self.details
        }


@dataclass
class ServiceMetrics:
    """Metrics for a monitored service."""
    service_id: str
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    active_connections: int = 0
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_id": self.service_id,
            "error_rate": self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "active_connections": self.active_connections,
            "last_updated": self.last_updated
        }


class FaultDetector:
    """Detects and tracks system faults.
    
    Features:
    - Multi-metric fault detection
    - Configurable thresholds per service
    - Fault severity classification
    - Automatic fault resolution tracking
    - Alert callbacks
    - Cascading failure detection
    """

    DEFAULT_THRESHOLDS = {
        "error_rate": 0.05,          # 5% error rate
        "latency_ms": 2000.0,        # 2 seconds
        "cpu_percent": 85.0,         # 85% CPU
        "memory_percent": 90.0,      # 90% memory
    }

    def __init__(self):
        """Initialize fault detector."""
        self.service_thresholds: Dict[str, Dict[str, float]] = {}
        self.active_faults: Dict[str, FaultEvent] = {}
        self.fault_history: List[FaultEvent] = []
        self.service_metrics: Dict[str, ServiceMetrics] = {}
        self._fault_counter = 0
        self._lock = threading.RLock()
        self._alert_callback: Optional[Callable[[FaultEvent], None]] = None
        self._resolve_callback: Optional[Callable[[FaultEvent], None]] = None

    def register_service(
        self,
        service_id: str,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """Register a service for monitoring.
        
        Args:
            service_id: Service identifier
            thresholds: Custom thresholds (uses defaults if not provided)
        """
        with self._lock:
            self.service_thresholds[service_id] = {
                **self.DEFAULT_THRESHOLDS,
                **(thresholds or {})
            }
            self.service_metrics[service_id] = ServiceMetrics(service_id=service_id)

    def update_metrics(self, service_id: str, metrics: Dict[str, float]) -> List[FaultEvent]:
        """Update service metrics and check for faults.
        
        Args:
            service_id: Service identifier
            metrics: Current metrics dict
            
        Returns:
            List of newly detected faults
        """
        with self._lock:
            if service_id not in self.service_metrics:
                self.register_service(service_id)

            # Update service metrics
            sm = self.service_metrics[service_id]
            if "error_rate" in metrics:
                sm.error_rate = metrics["error_rate"]
            if "latency_ms" in metrics:
                sm.avg_latency_ms = metrics["latency_ms"]
            if "cpu_percent" in metrics:
                sm.cpu_percent = metrics["cpu_percent"]
            if "memory_percent" in metrics:
                sm.memory_percent = metrics["memory_percent"]
            if "active_connections" in metrics:
                sm.active_connections = int(metrics["active_connections"])
            sm.last_updated = datetime.utcnow().isoformat()

            # Check for faults
            new_faults = self._check_faults(service_id, metrics)

            # Check for resolved faults
            self._check_resolutions(service_id, metrics)

            return new_faults

    def resolve_fault(self, fault_id: str) -> bool:
        """Mark a fault as resolved.
        
        Args:
            fault_id: Fault to resolve (fault_id field of FaultEvent)
            
        Returns:
            True if fault was resolved
        """
        with self._lock:
            # Find fault by its fault_id field (not the dict key)
            fault_key = None
            for key, fault in self.active_faults.items():
                if fault.fault_id == fault_id:
                    fault_key = key
                    break

            if fault_key is None:
                return False

            fault = self.active_faults[fault_key]
            fault.resolved = True
            fault.resolved_at = datetime.utcnow().isoformat()
            del self.active_faults[fault_key]

            if self._resolve_callback:
                self._resolve_callback(fault)

            return True

    def set_alert_callback(self, callback: Callable[[FaultEvent], None]) -> None:
        """Set callback for new fault alerts.
        
        Args:
            callback: Called with FaultEvent when fault is detected
        """
        self._alert_callback = callback

    def set_resolve_callback(self, callback: Callable[[FaultEvent], None]) -> None:
        """Set callback for fault resolution.
        
        Args:
            callback: Called with FaultEvent when fault is resolved
        """
        self._resolve_callback = callback

    def get_active_faults(self, service_id: Optional[str] = None) -> List[FaultEvent]:
        """Get active (unresolved) faults.
        
        Args:
            service_id: Filter by service (None = all services)
            
        Returns:
            List of active faults
        """
        with self._lock:
            faults = list(self.active_faults.values())
            if service_id:
                faults = [f for f in faults if f.service_id == service_id]
            return faults

    def get_fault_history(
        self,
        service_id: Optional[str] = None,
        fault_type: Optional[FaultType] = None
    ) -> List[FaultEvent]:
        """Get fault history with optional filtering.
        
        Args:
            service_id: Filter by service
            fault_type: Filter by fault type
            
        Returns:
            Filtered fault history
        """
        with self._lock:
            history = self.fault_history.copy()
            if service_id:
                history = [f for f in history if f.service_id == service_id]
            if fault_type:
                history = [f for f in history if f.fault_type == fault_type]
            return history

    def get_service_health(self, service_id: str) -> Dict[str, Any]:
        """Get health summary for a service.
        
        Args:
            service_id: Service identifier
            
        Returns:
            Health summary dict
        """
        with self._lock:
            active = [f for f in self.active_faults.values() if f.service_id == service_id]
            critical = [f for f in active if f.severity == FaultSeverity.CRITICAL]

            if critical:
                status = "critical"
            elif active:
                status = "degraded"
            else:
                status = "healthy"

            metrics = self.service_metrics.get(service_id)
            return {
                "service_id": service_id,
                "status": status,
                "active_faults": len(active),
                "critical_faults": len(critical),
                "metrics": metrics.to_dict() if metrics else {}
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get fault detector statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            critical_faults = sum(
                1 for f in self.active_faults.values()
                if f.severity == FaultSeverity.CRITICAL
            )
            return {
                "monitored_services": len(self.service_thresholds),
                "active_faults": len(self.active_faults),
                "critical_faults": critical_faults,
                "total_fault_history": len(self.fault_history),
                "resolved_faults": sum(1 for f in self.fault_history if f.resolved)
            }

    def _check_faults(self, service_id: str, metrics: Dict[str, float]) -> List[FaultEvent]:
        """Check metrics against thresholds to detect new faults."""
        thresholds = self.service_thresholds.get(service_id, self.DEFAULT_THRESHOLDS)
        new_faults = []

        checks = [
            ("error_rate", "error_rate", FaultType.HIGH_ERROR_RATE, FaultSeverity.ERROR),
            ("latency_ms", "latency_ms", FaultType.HIGH_LATENCY, FaultSeverity.WARNING),
            ("cpu_percent", "cpu_percent", FaultType.RESOURCE_EXHAUSTION, FaultSeverity.WARNING),
            ("memory_percent", "memory_percent", FaultType.RESOURCE_EXHAUSTION, FaultSeverity.WARNING)
        ]

        for metric_key, threshold_key, fault_type, severity in checks:
            if metric_key not in metrics:
                continue
            value = metrics[metric_key]
            threshold = thresholds.get(threshold_key, float('inf'))

            if value > threshold:
                # Check if fault already active
                fault_key = f"{service_id}:{fault_type.value}"
                if fault_key not in self.active_faults:
                    self._fault_counter += 1
                    fault = FaultEvent(
                        fault_id=f"fault_{self._fault_counter}",
                        fault_type=fault_type,
                        severity=severity,
                        service_id=service_id,
                        metric_value=value,
                        threshold=threshold,
                        details={metric_key: value}
                    )
                    self.active_faults[fault_key] = fault
                    self.fault_history.append(fault)
                    new_faults.append(fault)

                    if self._alert_callback:
                        self._alert_callback(fault)

        return new_faults

    def _check_resolutions(self, service_id: str, metrics: Dict[str, float]) -> None:
        """Check if any active faults have been resolved."""
        thresholds = self.service_thresholds.get(service_id, self.DEFAULT_THRESHOLDS)

        metric_to_fault = {
            "error_rate": FaultType.HIGH_ERROR_RATE,
            "latency_ms": FaultType.HIGH_LATENCY,
        }

        for metric_key, fault_type in metric_to_fault.items():
            if metric_key not in metrics:
                continue
            value = metrics[metric_key]
            threshold_key = metric_key
            threshold = thresholds.get(threshold_key, float('inf'))

            if value <= threshold * 0.8:  # 20% hysteresis
                fault_key = f"{service_id}:{fault_type.value}"
                if fault_key in self.active_faults:
                    self.resolve_fault(self.active_faults[fault_key].fault_id)
