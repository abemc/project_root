"""
Audit Logger: エージェント実行の完全な監査ログ

すべてのアクション（推論、ツール実行、意思決定）を記録し、
トレーサビリティと説明責任を確保。
"""

import logging
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path
from enum import Enum


class AuditEventType(Enum):
    """監査ログのイベント種別"""
    TASK_START = "task_start"
    TASK_END = "task_end"
    THINKING_STEP = "thinking_step"
    TOOL_SELECTED = "tool_selected"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    ERROR_OCCURRED = "error_occurred"
    FEEDBACK_RECEIVED = "feedback_received"
    MEMORY_ACCESSED = "memory_accessed"
    DECISION_MADE = "decision_made"


class ApprovalStatus(Enum):
    """承認ステータス"""
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AuditLogger:
    """エージェント実行監査ログ管理"""
    
    def __init__(
        self,
        log_dir: str = "logs",
        agent_id: str = "default_agent",
        enable_console: bool = True,
    ):
        """
        初期化
        
        Args:
            log_dir: ログ出力ディレクトリ
            agent_id: エージェント識別子
            enable_console: コンソール出力の有効化
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.agent_id = agent_id
        self.audit_file = self.log_dir / f"audit_{agent_id}.jsonl"
        self.summary_file = self.log_dir / f"audit_summary_{agent_id}.json"
        
        # ロガーセットアップ
        self.logger = logging.getLogger(f"audit.{agent_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # ファイルハンドラ（JSONL）
        file_handler = logging.FileHandler(self.audit_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(file_handler)
        
        # コンソールハンドラ
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(
                logging.Formatter('[%(asctime)s] [%(name)s] %(levelname)s: %(message)s')
            )
            self.logger.addHandler(console_handler)
        
        # 統計情報
        self.stats = {
            'total_events': 0,
            'events_by_type': {},
            'tool_executions': 0,
            'errors': 0,
            'approvals_required': 0,
            'approvals_granted': 0,
            'approvals_denied': 0,
            'start_time': datetime.now().isoformat(),
        }
    
    def log_event(
        self,
        event_type: AuditEventType,
        task_id: str,
        details: Dict[str, Any],
        severity: str = "INFO",
    ) -> str:
        """
        監査ログイベントを記録
        
        Args:
            event_type: イベント種別
            task_id: タスク ID
            details: イベント詳細
            severity: ログレベル (DEBUG, INFO, WARNING, ERROR)
        
        Returns:
            イベント ID
        """
        event_id = f"{task_id}_{datetime.now().timestamp()}"
        
        log_entry = {
            'event_id': event_id,
            'agent_id': self.agent_id,
            'event_type': event_type.value,
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'details': details,
            'severity': severity,
        }
        
        # ログに記録
        self.logger.log(
            getattr(logging, severity),
            json.dumps(log_entry, ensure_ascii=False)
        )
        
        # 統計更新
        self.stats['total_events'] += 1
        self.stats['events_by_type'][event_type.value] = (
            self.stats['events_by_type'].get(event_type.value, 0) + 1
        )
        
        return event_id
    
    def log_task_start(
        self,
        task_id: str,
        goal: str,
        autonomy_level: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """タスク開始イベント"""
        details = {
            'goal': goal,
            'autonomy_level': autonomy_level,
            'metadata': metadata or {},
        }
        return self.log_event(AuditEventType.TASK_START, task_id, details)
    
    def log_task_end(
        self,
        task_id: str,
        success: bool,
        result: Optional[str],
        duration_seconds: float,
    ) -> str:
        """タスク終了イベント"""
        details = {
            'success': success,
            'result': result,
            'duration_seconds': duration_seconds,
        }
        severity = "INFO" if success else "WARNING"
        return self.log_event(AuditEventType.TASK_END, task_id, details, severity)
    
    def log_thinking_step(
        self,
        task_id: str,
        step_number: int,
        reasoning: str,
        confidence: float,
    ) -> str:
        """推論ステップのログ"""
        details = {
            'step_number': step_number,
            'reasoning': reasoning[:500],  # 最初の 500 文字まで
            'confidence': confidence,
        }
        return self.log_event(AuditEventType.THINKING_STEP, task_id, details)
    
    def log_tool_selected(
        self,
        task_id: str,
        tool_name: str,
        reason: str,
        alternatives: Optional[List[str]] = None,
    ) -> str:
        """ツール選択のログ"""
        details = {
            'tool_name': tool_name,
            'reason': reason,
            'alternatives': alternatives or [],
        }
        return self.log_event(AuditEventType.TOOL_SELECTED, task_id, details)
    
    def log_tool_execution(
        self,
        task_id: str,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        output: Optional[Any] = None,
        error: Optional[str] = None,
        duration_seconds: float = 0.0,
    ) -> str:
        """ツール実行のログ"""
        details = {
            'tool_name': tool_name,
            'params': {k: v for k, v in params.items() if k != 'password'},  # 機密情報除外
            'success': success,
            'output': str(output)[:200] if output else None,
            'error': error,
            'duration_seconds': duration_seconds,
        }
        
        severity = "INFO" if success else "ERROR"
        event_id = self.log_event(
            AuditEventType.TOOL_EXECUTION_END if success else AuditEventType.TOOL_EXECUTION_END,
            task_id,
            details,
            severity
        )
        
        self.stats['tool_executions'] += 1
        if not success:
            self.stats['errors'] += 1
        
        return event_id
    
    def log_approval_required(
        self,
        task_id: str,
        tool_name: str,
        reason: str,
        suggested_action: str,
    ) -> str:
        """承認要求のログ"""
        details = {
            'tool_name': tool_name,
            'reason': reason,
            'suggested_action': suggested_action,
            'approval_status': ApprovalStatus.PENDING.value,
        }
        self.log_event(AuditEventType.APPROVAL_REQUIRED, task_id, details, "WARNING")
        self.stats['approvals_required'] += 1
        return task_id
    
    def log_approval_decision(
        self,
        task_id: str,
        tool_name: str,
        approved: bool,
        user_comment: Optional[str] = None,
    ) -> str:
        """承認判定のログ"""
        event_type = (
            AuditEventType.APPROVAL_GRANTED
            if approved
            else AuditEventType.APPROVAL_DENIED
        )
        
        details = {
            'tool_name': tool_name,
            'approved': approved,
            'user_comment': user_comment,
        }
        
        severity = "INFO" if approved else "WARNING"
        event_id = self.log_event(event_type, task_id, details, severity)
        
        if approved:
            self.stats['approvals_granted'] += 1
        else:
            self.stats['approvals_denied'] += 1
        
        return event_id
    
    def log_error(
        self,
        task_id: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """エラーイベントのログ"""
        details = {
            'error_type': error_type,
            'error_message': error_message,
            'context': context or {},
        }
        self.stats['errors'] += 1
        return self.log_event(AuditEventType.ERROR_OCCURRED, task_id, details, "ERROR")
    
    def log_feedback(
        self,
        task_id: str,
        feedback_type: str,
        feedback_text: str,
        correction_hint: Optional[str] = None,
    ) -> str:
        """ユーザーフィードバックのログ"""
        details = {
            'feedback_type': feedback_type,  # "correction", "praise", "clarification"
            'feedback_text': feedback_text,
            'correction_hint': correction_hint,
        }
        return self.log_event(AuditEventType.FEEDBACK_RECEIVED, task_id, details)
    
    def log_memory_access(
        self,
        task_id: str,
        memory_type: str,
        query: str,
        results_count: int,
    ) -> str:
        """メモリアクセスのログ"""
        details = {
            'memory_type': memory_type,  # "episodic", "semantic", "procedural"
            'query': query,
            'results_count': results_count,
        }
        return self.log_event(AuditEventType.MEMORY_ACCESSED, task_id, details)
    
    def log_decision(
        self,
        task_id: str,
        decision_type: str,
        decision: str,
        reasoning: str,
        alternatives: Optional[List[str]] = None,
        confidence: float = 0.5,
    ) -> str:
        """意思決定のログ"""
        details = {
            'decision_type': decision_type,  # "next_action", "parameter_selection", "tool_choice"
            'decision': decision,
            'reasoning': reasoning,
            'alternatives': alternatives or [],
            'confidence': confidence,
        }
        return self.log_event(AuditEventType.DECISION_MADE, task_id, details)
    
    def get_task_audit_trail(self, task_id: str) -> List[Dict[str, Any]]:
        """タスク ID のすべての監査ログエントリを取得"""
        trail = []
        
        if not self.audit_file.exists():
            return trail
        
        try:
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get('task_id') == task_id:
                            trail.append(entry)
        except Exception as e:
            self.logger.error(f"Failed to read audit trail: {e}")
        
        return trail
    
    def export_summary(self) -> Dict[str, Any]:
        """監査統計サマリーをエクスポート"""
        summary = {
            'agent_id': self.agent_id,
            'summary': self.stats,
            'end_time': datetime.now().isoformat(),
        }
        
        try:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Audit summary exported to {self.summary_file}")
        except Exception as e:
            self.logger.error(f"Failed to export audit summary: {e}")
        
        return summary
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return self.stats.copy()
