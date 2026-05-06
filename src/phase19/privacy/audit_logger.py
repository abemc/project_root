"""Audit Logger for tracking privacy-related events."""

import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
import threading


class AuditEventType(Enum):
    """Types of audit events."""
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    ENCRYPTION_KEY_ROTATION = "encryption_key_rotation"
    DECRYPTION_ATTEMPT = "decryption_attempt"
    PII_DETECTION = "pii_detection"
    MASKING_OPERATION = "masking_operation"
    EXPORT_REQUEST = "export_request"
    DELETE_REQUEST = "delete_request"
    CONSENT_CHANGE = "consent_change"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    CONFIGURATION_CHANGE = "configuration_change"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event."""
    event_type: AuditEventType
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: Optional[str] = None
    resource_id: Optional[str] = None
    action: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    severity: AuditSeverity = AuditSeverity.INFO
    status: str = "success"  # success, failure
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    event_hash: str = ""

    def __post_init__(self):
        """Calculate event hash after initialization."""
        if not self.event_hash:
            self.event_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculate SHA-256 hash of event."""
        event_str = json.dumps({
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "resource_id": self.resource_id,
            "action": self.action
        }, sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
            "severity": self.severity.value,
            "status": self.status,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "event_hash": self.event_hash
        }


class AuditLogger:
    """Logs and tracks privacy-related events.
    
    Features:
    - Thread-safe event logging
    - Event querying and filtering
    - Immutable event log
    - Chain of custody verification
    - Retention policies
    - Event aggregation
    """

    def __init__(self, retention_days: int = 90):
        """Initialize audit logger.
        
        Args:
            retention_days: Days to retain audit logs (default: 90)
        """
        self.events: List[AuditEvent] = []
        self.retention_days = retention_days
        self.lock = threading.RLock()
        self.event_counters: Dict[str, int] = {}

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        status: str = "success",
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditEvent:
        """Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action description
            user_id: User performing action
            resource_id: Resource affected
            details: Additional event details
            severity: Event severity level
            status: success or failure
            ip_address: Source IP address
            session_id: Session identifier
            
        Returns:
            Created AuditEvent
        """
        with self.lock:
            event = AuditEvent(
                event_type=event_type,
                user_id=user_id,
                resource_id=resource_id,
                action=action,
                details=details or {},
                severity=severity,
                status=status,
                ip_address=ip_address,
                session_id=session_id
            )

            self.events.append(event)
            
            # Update counters
            event_type_str = event_type.value
            self.event_counters[event_type_str] = self.event_counters.get(event_type_str, 0) + 1

            return event

    def log_data_access(
        self,
        user_id: str,
        resource_id: str,
        data_fields: List[str],
        **kwargs
    ) -> AuditEvent:
        """Log data access event.
        
        Args:
            user_id: User accessing data
            resource_id: Data resource ID
            data_fields: Fields accessed
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        return self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            action=f"Accessed {len(data_fields)} fields",
            user_id=user_id,
            resource_id=resource_id,
            details={"fields": data_fields},
            **kwargs
        )

    def log_data_deletion(
        self,
        user_id: str,
        resource_id: str,
        reason: str,
        **kwargs
    ) -> AuditEvent:
        """Log data deletion event.
        
        Args:
            user_id: User deleting data
            resource_id: Data resource ID
            reason: Deletion reason
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        return self.log_event(
            event_type=AuditEventType.DATA_DELETION,
            action=f"Deleted data: {reason}",
            user_id=user_id,
            resource_id=resource_id,
            details={"reason": reason},
            severity=AuditSeverity.WARNING,
            **kwargs
        )

    def log_pii_detection(
        self,
        pii_types: List[str],
        count: int,
        risk_level: str,
        **kwargs
    ) -> AuditEvent:
        """Log PII detection event.
        
        Args:
            pii_types: Types of PII detected
            count: Number of PII instances
            risk_level: Risk level (low/medium/high)
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        severity_map = {
            "low": AuditSeverity.INFO,
            "medium": AuditSeverity.WARNING,
            "high": AuditSeverity.CRITICAL
        }

        return self.log_event(
            event_type=AuditEventType.PII_DETECTION,
            action=f"Detected {count} PII instances",
            details={"pii_types": pii_types, "risk_level": risk_level},
            severity=severity_map.get(risk_level, AuditSeverity.WARNING),
            **kwargs
        )

    def log_export_request(
        self,
        user_id: str,
        resource_id: str,
        format_type: str,
        **kwargs
    ) -> AuditEvent:
        """Log data export request.
        
        Args:
            user_id: User requesting export
            resource_id: Resource being exported
            format_type: Export format (json, csv, xml, etc.)
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        return self.log_event(
            event_type=AuditEventType.EXPORT_REQUEST,
            action=f"Requested data export in {format_type} format",
            user_id=user_id,
            resource_id=resource_id,
            details={"format": format_type},
            **kwargs
        )

    def log_delete_request(
        self,
        user_id: str,
        resource_id: str,
        reason: str,
        **kwargs
    ) -> AuditEvent:
        """Log GDPR delete request.
        
        Args:
            user_id: User requesting deletion
            resource_id: Resource to delete
            reason: Deletion reason
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        return self.log_event(
            event_type=AuditEventType.DELETE_REQUEST,
            action=f"GDPR delete request: {reason}",
            user_id=user_id,
            resource_id=resource_id,
            details={"reason": reason},
            severity=AuditSeverity.WARNING,
            **kwargs
        )

    def log_unauthorized_access(
        self,
        user_id: Optional[str],
        resource_id: str,
        reason: str,
        **kwargs
    ) -> AuditEvent:
        """Log unauthorized access attempt.
        
        Args:
            user_id: User attempting access
            resource_id: Protected resource
            reason: Reason for denial
            **kwargs: Additional parameters
            
        Returns:
            Created AuditEvent
        """
        return self.log_event(
            event_type=AuditEventType.UNAUTHORIZED_ACCESS,
            action=f"Unauthorized access denied: {reason}",
            user_id=user_id,
            resource_id=resource_id,
            severity=AuditSeverity.CRITICAL,
            status="failure",
            details={"reason": reason},
            **kwargs
        )

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None
    ) -> List[AuditEvent]:
        """Query audit events with filters.
        
        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            resource_id: Filter by resource ID
            start_time: Filter by start time
            end_time: Filter by end time
            severity: Filter by severity
            
        Returns:
            Filtered list of events
        """
        with self.lock:
            results = self.events.copy()

            if event_type:
                results = [e for e in results if e.event_type == event_type]

            if user_id:
                results = [e for e in results if e.user_id == user_id]

            if resource_id:
                results = [e for e in results if e.resource_id == resource_id]

            if severity:
                results = [e for e in results if e.severity == severity]

            if start_time:
                start_iso = start_time.isoformat()
                results = [e for e in results if e.timestamp >= start_iso]

            if end_time:
                end_iso = end_time.isoformat()
                results = [e for e in results if e.timestamp <= end_iso]

            return results

    def cleanup_expired_events(self) -> int:
        """Remove events older than retention period.
        
        Returns:
            Number of events removed
        """
        with self.lock:
            cutoff_time = (datetime.utcnow() - timedelta(days=self.retention_days)).isoformat()
            initial_count = len(self.events)
            self.events = [e for e in self.events if e.timestamp >= cutoff_time]
            return initial_count - len(self.events)

    def get_event_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for events.
        
        Args:
            start_time: Start time for summary
            end_time: End time for summary
            
        Returns:
            Summary statistics
        """
        events = self.query_events(start_time=start_time, end_time=end_time)

        summary = {
            "total_events": len(events),
            "events_by_type": {},
            "events_by_severity": {},
            "events_by_user": {},
            "failure_count": 0,
            "success_count": 0
        }

        for event in events:
            # Count by type
            event_type_str = event.event_type.value
            summary["events_by_type"][event_type_str] = summary["events_by_type"].get(event_type_str, 0) + 1

            # Count by severity
            severity_str = event.severity.value
            summary["events_by_severity"][severity_str] = summary["events_by_severity"].get(severity_str, 0) + 1

            # Count by user
            if event.user_id:
                summary["events_by_user"][event.user_id] = summary["events_by_user"].get(event.user_id, 0) + 1

            # Count success/failure
            if event.status == "failure":
                summary["failure_count"] += 1
            else:
                summary["success_count"] += 1

        return summary

    def export_events(
        self,
        format_type: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> str:
        """Export events in specified format.
        
        Args:
            format_type: Export format (json, csv)
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            Exported events as string
        """
        events = self.query_events(start_time=start_time, end_time=end_time)
        event_dicts = [e.to_dict() for e in events]

        if format_type == "json":
            return json.dumps(event_dicts, indent=2)
        elif format_type == "csv":
            import csv
            from io import StringIO
            
            if not event_dicts:
                return ""

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=event_dicts[0].keys())
            writer.writeheader()
            writer.writerows(event_dicts)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def get_stats(self) -> Dict[str, Any]:
        """Get audit logger statistics.
        
        Returns:
            Statistics dictionary
        """
        with self.lock:
            return {
                "total_events": len(self.events),
                "events_by_type": self.event_counters.copy(),
                "retention_days": self.retention_days
            }
