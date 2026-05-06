"""
監査ログ実装

操作記録とコンプライアンス監査
- イベント記録
- ユーザートレース
- 監査レポート生成
- ストレージ管理
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)


class EventType(Enum):
    """イベントタイプ"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_DENIED = "access_denied"
    SECURITY_EVENT = "security_event"
    ERROR = "error"
    OTHER = "other"


class Severity(Enum):
    """イベント重大度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """監査イベント"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    user_id: str
    resource_type: str
    resource_id: str
    action: str
    status: str                         # "success", "failure"
    severity: Severity
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "severity": self.severity.value,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


@dataclass
class AuditMetrics:
    """監査メトリクス"""
    total_events: int = 0
    events_by_type: Dict[str, int] = field(default_factory=dict)
    events_by_severity: Dict[str, int] = field(default_factory=dict)
    events_by_user: Dict[str, int] = field(default_factory=dict)
    failed_events: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_events": self.total_events,
            "events_by_type": self.events_by_type,
            "events_by_severity": self.events_by_severity,
            "events_by_user": self.events_by_user,
            "failed_events": self.failed_events,
        }


class AuditLog:
    """監査ログシステム"""
    
    def __init__(self, max_events: int = 10000):
        """初期化"""
        self.max_events = max_events
        self.events: List[AuditEvent] = []
        self.metrics = AuditMetrics()
        self._event_counter = 0
    
    def log_event(
        self,
        event_type: EventType,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        status: str = "success",
        severity: Severity = Severity.INFO,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditEvent:
        """イベントを記録"""
        self._event_counter += 1
        event_id = f"EVT{self._event_counter:06d}"
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status=status,
            severity=severity,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # ログを保存
        self.events.append(event)
        
        # 最大数を超えた場合は古いイベントを削除
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # メトリクスを更新
        self._update_metrics(event)
        
        logger.info(
            f"Audit event: {event_type.value} {resource_type}/{resource_id} "
            f"by {user_id} - {status}"
        )
        
        return event
    
    def _update_metrics(self, event: AuditEvent) -> None:
        """メトリクスを更新"""
        self.metrics.total_events += 1
        
        # イベントタイプ別
        type_key = event.event_type.value
        self.metrics.events_by_type[type_key] = self.metrics.events_by_type.get(type_key, 0) + 1
        
        # 重大度別
        severity_key = event.severity.value
        self.metrics.events_by_severity[severity_key] = self.metrics.events_by_severity.get(severity_key, 0) + 1
        
        # ユーザー別
        user_key = event.user_id
        self.metrics.events_by_user[user_key] = self.metrics.events_by_user.get(user_key, 0) + 1
        
        # 失敗したイベント
        if event.status == "failure":
            self.metrics.failed_events += 1
    
    def log_create(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict] = None,
        **kwargs
    ) -> AuditEvent:
        """作成イベントを記録"""
        return self.log_event(
            event_type=EventType.CREATE,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="create",
            details=details,
            **kwargs
        )
    
    def log_read(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict] = None,
        **kwargs
    ) -> AuditEvent:
        """読取イベントを記録"""
        return self.log_event(
            event_type=EventType.READ,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="read",
            details=details,
            **kwargs
        )
    
    def log_update(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        changes: Optional[Dict] = None,
        **kwargs
    ) -> AuditEvent:
        """更新イベントを記録"""
        return self.log_event(
            event_type=EventType.UPDATE,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="update",
            details={"changes": changes} if changes else {},
            **kwargs
        )
    
    def log_delete(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict] = None,
        **kwargs
    ) -> AuditEvent:
        """削除イベントを記録"""
        return self.log_event(
            event_type=EventType.DELETE,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="delete",
            details=details,
            **kwargs
        )
    
    def log_security_event(
        self,
        user_id: str,
        action: str,
        severity: Severity = Severity.WARNING,
        details: Optional[Dict] = None,
        **kwargs
    ) -> AuditEvent:
        """セキュリティイベントを記録"""
        return self.log_event(
            event_type=EventType.SECURITY_EVENT,
            user_id=user_id,
            resource_type="security",
            resource_id=action,
            action=action,
            severity=severity,
            details=details,
            **kwargs
        )
    
    def query_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """イベントをクエリ"""
        results = self.events
        
        # ユーザーでフィルタ
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        
        # イベントタイプでフィルタ
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        
        # リソースタイプでフィルタ
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        
        # 時間範囲でフィルタ
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        
        # 逆時系列でソート
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        
        # 制限を適用
        return results[:limit]
    
    def get_user_audit_trail(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """ユーザーの監査証跡を取得"""
        events = self.query_events(user_id=user_id, limit=limit)
        return [e.to_dict() for e in events]
    
    def get_resource_audit_trail(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """リソースの監査証跡を取得"""
        events = self.query_events(
            resource_type=resource_type,
            limit=limit
        )
        events = [e for e in events if e.resource_id == resource_id]
        return [e.to_dict() for e in events]
    
    def generate_audit_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """監査レポートを生成"""
        if start_time is None:
            start_time = datetime.now() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now()
        
        events = self.query_events(
            start_time=start_time,
            end_time=end_time,
            limit=999999
        )
        
        # 統計情報を集計
        total_events = len(events)
        success_count = sum(1 for e in events if e.status == "success")
        failure_count = sum(1 for e in events if e.status == "failure")
        
        # イベントタイプ別
        by_type = {}
        for event in events:
            type_key = event.event_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
        
        # 重大度別
        by_severity = {}
        for event in events:
            severity_key = event.severity.value
            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1
        
        # ユーザー別
        by_user = {}
        for event in events:
            user_key = event.user_id
            by_user[user_key] = by_user.get(user_key, 0) + 1
        
        return {
            "report_generated": datetime.now().isoformat(),
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "total_events": total_events,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": (success_count / total_events * 100) if total_events > 0 else 0,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_user": by_user,
            "top_users": sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10],
        }
    
    def export_events(self, file_path: str) -> None:
        """イベントをJSONファイルにエクスポート"""
        data = [e.to_dict() for e in self.events]
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Exported {len(data)} events to {file_path}")
    
    def get_metrics(self) -> AuditMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """メトリクスを辞書形式で取得"""
        return self.metrics.to_dict()
    
    def clear_old_events(self, days: int = 90) -> int:
        """古いイベントを削除"""
        cutoff_date = datetime.now() - timedelta(days=days)
        original_count = len(self.events)
        self.events = [e for e in self.events if e.timestamp > cutoff_date]
        deleted_count = original_count - len(self.events)
        logger.info(f"Deleted {deleted_count} events older than {days} days")
        return deleted_count


# グローバルインスタンス
_global_audit_log: Optional[AuditLog] = None


def get_audit_log() -> AuditLog:
    """グローバル監査ログを取得"""
    global _global_audit_log
    if _global_audit_log is None:
        _global_audit_log = AuditLog()
    return _global_audit_log
