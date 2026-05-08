"""
エージェントタスク成功追跡モジュール

タスク実行の成功/失敗を追跡し、パターン分析を行います：
- タスク分類別成功率
- 複数段階タスクの完成率
- リトライ回数・効率
- エラーパターン分析
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from datetime import datetime
from collections import Counter, defaultdict


class TaskStatus(Enum):
    """タスクのステータス"""
    PENDING = "pending"                # 待機中
    IN_PROGRESS = "in_progress"        # 実行中
    COMPLETED = "completed"            # 完了
    FAILED = "failed"                  # 失敗
    ABANDONED = "abandoned"            # 中止


class TaskType(Enum):
    """タスクの種類"""
    SIMPLE = "simple"                  # 単純タスク（1ステップ）
    MULTI_STEP = "multi_step"          # マルチステップ
    COMPLEX = "complex"                # 複雑なタスク
    REASONING = "reasoning"            # 推論タスク
    CREATIVE = "creative"              # 創造的タスク


class ErrorCategory(Enum):
    """エラーのカテゴリ"""
    LOGIC_ERROR = "logic_error"        # 論理エラー
    RESOURCE_ERROR = "resource_error"  # リソース不足
    TIMEOUT_ERROR = "timeout_error"    # タイムアウト
    TOOL_ERROR = "tool_error"          # ツール呼び出しエラー
    UNKNOWN_ERROR = "unknown_error"    # 不明なエラー


@dataclass
class TaskAttempt:
    """単一のタスク試行"""
    attempt_number: int
    status: TaskStatus
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    duration: Optional[float] = None   # 実行時間（秒）
    steps_taken: int = 0               # 実行ステップ数
    recovery_attempts: int = 0         # 復旧試行回数
    
    def is_successful(self) -> bool:
        """成功かどうか"""
        return self.status == TaskStatus.COMPLETED
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "attempt": self.attempt_number,
            "status": self.status.value,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "steps": self.steps_taken,
            "error": self.error,
            "recovery": self.recovery_attempts,
        }


@dataclass
class TaskRecord:
    """タスク実行の完全な記録"""
    task_id: str
    task_description: str
    task_type: TaskType
    attempts: List[TaskAttempt] = field(default_factory=list)
    final_status: TaskStatus = TaskStatus.PENDING
    total_duration: Optional[float] = None
    final_result: str = ""              # 最終結果
    complexity_estimate: int = 1        # 推定複雑度（1-10）
    
    def add_attempt(self, attempt: TaskAttempt) -> None:
        """試行を追加"""
        self.attempts.append(attempt)
    
    def is_successful(self) -> bool:
        """成功したかどうか"""
        return self.final_status == TaskStatus.COMPLETED
    
    def get_attempt_count(self) -> int:
        """試行回数"""
        return len(self.attempts)
    
    def get_success_rate(self) -> float:
        """成功率 (0-1)"""
        if not self.attempts:
            return 0.0
        
        successful = sum(1 for attempt in self.attempts if attempt.is_successful())
        return successful / len(self.attempts)
    
    def get_average_attempt_duration(self) -> Optional[float]:
        """平均試行時間"""
        durations = [a.duration for a in self.attempts if a.duration is not None]
        if not durations:
            return None
        return sum(durations) / len(durations)
    
    def get_total_recovery_attempts(self) -> int:
        """総復旧試行回数"""
        return sum(attempt.recovery_attempts for attempt in self.attempts)
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "task_id": self.task_id,
            "description": self.task_description,
            "type": self.task_type.value,
            "status": self.final_status.value,
            "success": self.is_successful(),
            "attempts": self.get_attempt_count(),
            "attempts_detail": [a.to_dict() for a in self.attempts],
            "duration": self.total_duration,
            "complexity": self.complexity_estimate,
            "recovery": self.get_total_recovery_attempts(),
        }


class TaskSuccessTracker:
    """タスク成功追跡エンジン"""
    
    def __init__(self):
        """初期化"""
        self.tasks: List[TaskRecord] = []
        self.error_patterns: Dict[str, List[str]] = defaultdict(list)
    
    def create_task(
        self,
        task_id: str,
        task_description: str,
        task_type: TaskType,
        complexity_estimate: int = 1,
    ) -> TaskRecord:
        """新しいタスク記録を作成"""
        record = TaskRecord(
            task_id=task_id,
            task_description=task_description,
            task_type=task_type,
            complexity_estimate=min(10, max(1, complexity_estimate)),
        )
        return record
    
    def record_attempt(
        self,
        task_record: TaskRecord,
        status: TaskStatus,
        start_time: str,
        end_time: Optional[str] = None,
        error: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        duration: Optional[float] = None,
        steps_taken: int = 0,
    ) -> TaskAttempt:
        """タスク試行を記録"""
        attempt = TaskAttempt(
            attempt_number=len(task_record.attempts) + 1,
            status=status,
            start_time=start_time,
            end_time=end_time,
            error=error,
            error_category=error_category,
            duration=duration,
            steps_taken=steps_taken,
        )
        
        task_record.add_attempt(attempt)
        
        # エラーパターン記録
        if error and error_category:
            self.error_patterns[error_category.value].append(task_record.task_id)
        
        return attempt
    
    def complete_task(
        self,
        task_record: TaskRecord,
        final_status: TaskStatus,
        final_result: str = "",
    ) -> None:
        """タスクを完了"""
        task_record.final_status = final_status
        task_record.final_result = final_result
        
        # 総実行時間を計算
        if task_record.attempts:
            total_duration = sum(
                a.duration for a in task_record.attempts
                if a.duration is not None
            )
            task_record.total_duration = total_duration
        
        self.tasks.append(task_record)
    
    def record_recovery(self, attempt: TaskAttempt) -> None:
        """復旧試行を記録"""
        attempt.recovery_attempts += 1
    
    def get_overall_success_rate(self) -> float:
        """全体的な成功率 (0-1)"""
        if not self.tasks:
            return 0.0
        
        successful = sum(1 for task in self.tasks if task.is_successful())
        return successful / len(self.tasks)
    
    def get_success_rate_by_type(self) -> Dict[str, float]:
        """タスクタイプ別成功率"""
        tasks_by_type = defaultdict(list)
        
        for task in self.tasks:
            tasks_by_type[task.task_type.value].append(task)
        
        success_rates = {}
        for task_type, tasks in tasks_by_type.items():
            successful = sum(1 for t in tasks if t.is_successful())
            success_rates[task_type] = successful / len(tasks) if tasks else 0.0
        
        return success_rates
    
    def get_success_rate_by_complexity(self) -> Dict[int, float]:
        """複雑度別成功率"""
        tasks_by_complexity = defaultdict(list)
        
        for task in self.tasks:
            tasks_by_complexity[task.complexity_estimate].append(task)
        
        success_rates = {}
        for complexity, tasks in tasks_by_complexity.items():
            successful = sum(1 for t in tasks if t.is_successful())
            success_rates[complexity] = successful / len(tasks) if tasks else 0.0
        
        return success_rates
    
    def get_multi_step_completion_rate(self) -> float:
        """複数段階タスク完成率（推奨値: 85%+）"""
        multi_step_tasks = [
            t for t in self.tasks
            if t.task_type in [TaskType.MULTI_STEP, TaskType.COMPLEX]
        ]
        
        if not multi_step_tasks:
            return 0.0
        
        completed = sum(1 for t in multi_step_tasks if t.is_successful())
        return completed / len(multi_step_tasks)
    
    def get_error_pattern_analysis(self) -> Dict:
        """エラーパターン分析"""
        if not self.error_patterns:
            return {}
        
        analysis = {}
        total_errors = sum(len(tasks) for tasks in self.error_patterns.values())
        
        for error_category, task_ids in self.error_patterns.items():
            analysis[error_category] = {
                "count": len(task_ids),
                "percentage": len(task_ids) / total_errors * 100 if total_errors > 0 else 0,
                "tasks": task_ids,
            }
        
        return analysis
    
    def get_most_common_errors(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """最も一般的なエラーを取得"""
        error_counts = Counter()
        
        for task in self.tasks:
            for attempt in task.attempts:
                if attempt.error_category:
                    error_counts[attempt.error_category.value] += 1
        
        return error_counts.most_common(top_n)
    
    def get_retry_statistics(self) -> Dict:
        """リトライ統計"""
        if not self.tasks:
            return {}
        
        attempt_counts = [t.get_attempt_count() for t in self.tasks]
        
        return {
            "average_attempts": sum(attempt_counts) / len(attempt_counts),
            "max_attempts": max(attempt_counts),
            "min_attempts": min(attempt_counts),
            "tasks_needing_retry": sum(1 for count in attempt_counts if count > 1),
            "first_attempt_success_rate": (
                sum(1 for t in self.tasks if t.get_attempt_count() == 1 and t.is_successful())
                / len(self.tasks)
            ) if self.tasks else 0.0,
        }
    
    def get_recovery_statistics(self) -> Dict:
        """復旧試行統計"""
        total_recovery_attempts = sum(
            t.get_total_recovery_attempts() for t in self.tasks
        )
        
        tasks_with_recovery = sum(
            1 for t in self.tasks if t.get_total_recovery_attempts() > 0
        )
        
        return {
            "total_recovery_attempts": total_recovery_attempts,
            "tasks_with_recovery": tasks_with_recovery,
            "average_recovery_per_task": (
                total_recovery_attempts / len(self.tasks)
            ) if self.tasks else 0.0,
            "recovery_success_rate": (
                sum(1 for t in self.tasks if t.is_successful() and t.get_total_recovery_attempts() > 0)
                / tasks_with_recovery
            ) if tasks_with_recovery > 0 else 0.0,
        }
    
    def get_performance_metrics(self) -> Dict:
        """パフォーマンスメトリクスを取得"""
        if not self.tasks:
            return {}
        
        durations = [t.total_duration for t in self.tasks if t.total_duration is not None]
        
        return {
            "total_tasks": len(self.tasks),
            "overall_success_rate": self.get_overall_success_rate(),
            "multi_step_completion_rate": self.get_multi_step_completion_rate(),
            "success_by_type": self.get_success_rate_by_type(),
            "success_by_complexity": self.get_success_rate_by_complexity(),
            "retry_stats": self.get_retry_statistics(),
            "recovery_stats": self.get_recovery_statistics(),
            "error_patterns": self.get_error_pattern_analysis(),
            "average_duration": sum(durations) / len(durations) if durations else None,
        }
    
    def get_autonomy_readiness_score(self) -> float:
        """自律性準備度スコア (0-1)"""
        metrics = self.get_performance_metrics()
        
        if not metrics:
            return 0.0
        
        scores = {}
        
        # 成功率（40%）
        scores["success"] = metrics["overall_success_rate"] * 0.4
        
        # マルチステップ完成率（30%）
        scores["multi_step"] = metrics["multi_step_completion_rate"] * 0.3
        
        # リトライ効率（20%）
        retry_stats = metrics.get("retry_stats", {})
        first_attempt_success = retry_stats.get("first_attempt_success_rate", 0.5)
        scores["retry"] = first_attempt_success * 0.2
        
        # 復旧成功率（10%）
        recovery_stats = metrics.get("recovery_stats", {})
        recovery_success = recovery_stats.get("recovery_success_rate", 0.5)
        scores["recovery"] = recovery_success * 0.1
        
        return sum(scores.values())
    
    def export_summary(self) -> Dict:
        """サマリーをエクスポート"""
        return {
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks if t.is_successful()),
            "performance_metrics": self.get_performance_metrics(),
            "autonomy_readiness": self.get_autonomy_readiness_score(),
            "top_errors": self.get_most_common_errors(),
        }
    
    def reset_tracking(self):
        """追跡をリセット"""
        self.tasks = []
        self.error_patterns = defaultdict(list)
