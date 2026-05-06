"""
Phase 17 Task 3: Autonomous Agent Architecture

エージェント自律化エンジン
- タスク分解・計画
- ツール統合・実行
- 自己改善・学習
- リアルタイムモニタリング
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime
import json
import logging


class TaskStatus(Enum):
    """タスクの状態管理"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ToolType(Enum):
    """ツール種別分類"""
    INFORMATION = "information"  # Web検索, DB照会
    ACTION = "action"  # ファイル操作, API呼び出し
    REASONING = "reasoning"  # 計算, コード実行
    COMMUNICATION = "communication"  # 通知, メール


class AutonomyLevel(Enum):
    """エージェント自律レベル"""
    SUPERVISED = "supervised"  # 完全ユーザー監督
    SEMI_AUTONOMOUS = "semi_autonomous"  # ユーザー承認ポイント有
    AUTONOMOUS = "autonomous"  # 完全自律
    RESTRICTED = "restricted"  # 制限付き自律


@dataclass
class Tool:
    """ツール定義"""
    name: str
    tool_type: ToolType
    description: str
    execute_fn: Callable
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    require_approval: bool = False


@dataclass
class SubTask:
    """サブタスク定義"""
    task_id: str
    description: str
    required_tools: List[str] = field(default_factory=list)
    parent_task: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ExecutionPlan:
    """実行計画"""
    main_goal: str
    subtasks: List[SubTask] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    estimated_steps: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"


@dataclass
class ToolResult:
    """ツール実行結果"""
    tool_name: str
    status: str  # success, error, timeout
    result: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0
    confidence: float = 0.95


class TaskPlanner:
    """タスク分解・計画エンジン"""
    
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self.logger = logging.getLogger(__name__)
    
    def decompose_task(self, goal: str, context: Dict[str, Any]) -> ExecutionPlan:
        """
        ゴールを再帰的に分解して実行計画を作成
        
        Args:
            goal: 達成ゴール
            context: 利用可能ツール・制約情報
        
        Returns:
            ExecutionPlan: 実行計画
        """
        plan = ExecutionPlan(main_goal=goal)
        
        # ゴール分析
        complexity = self._analyze_complexity(goal)
        
        if complexity == "simple":
            # 単一ステップ
            subtask = SubTask(
                task_id="task_1",
                description=goal,
                required_tools=self._identify_required_tools(goal, context)
            )
            plan.subtasks = [subtask]
            plan.execution_order = ["task_1"]
        
        elif complexity == "moderate":
            # 複数ステップ分解
            subtasks = self._decompose_moderate(goal, context)
            plan.subtasks = subtasks
            plan.execution_order = self._topological_sort(subtasks)
        
        else:  # complex
            # 階層的分解
            subtasks = self._decompose_complex(goal, context, depth=0)
            plan.subtasks = subtasks
            plan.execution_order = self._topological_sort(subtasks)
        
        plan.estimated_steps = len(plan.execution_order)
        plan.status = "ready"
        
        return plan
    
    def _analyze_complexity(self, goal: str) -> str:
        """ゴール複雑性分析"""
        keywords_simple = ["search", "retrieve", "get", "list"]
        keywords_complex = ["plan", "optimize", "design", "create"]
        
        goal_lower = goal.lower()
        
        if any(kw in goal_lower for kw in keywords_complex):
            return "complex"
        elif any(kw in goal_lower for kw in keywords_simple):
            return "simple"
        else:
            return "moderate"
    
    def _identify_required_tools(self, goal: str, context: Dict) -> List[str]:
        """必要ツール特定"""
        required_tools = []
        
        if "search" in goal.lower() or "find" in goal.lower():
            required_tools.append("web_search")
        if "calculate" in goal.lower() or "compute" in goal.lower():
            required_tools.append("calculator")
        if "write" in goal.lower() or "create" in goal.lower():
            required_tools.append("file_writer")
        if "verify" in goal.lower() or "check" in goal.lower():
            required_tools.append("verifier")
        
        return required_tools
    
    def _decompose_moderate(self, goal: str, context: Dict) -> List[SubTask]:
        """中程度複雑性の分解"""
        subtasks = []
        
        # 3-5ステップに分解
        steps = [
            f"理解: {goal}",
            f"リソース準備",
            f"実行: {goal}",
            f"検証"
        ]
        
        for i, step in enumerate(steps):
            subtask = SubTask(
                task_id=f"task_{i+1}",
                description=step,
                dependencies=[] if i == 0 else [f"task_{i}"]
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _decompose_complex(self, goal: str, context: Dict, depth: int) -> List[SubTask]:
        """複雑なゴールの階層分解"""
        if depth >= self.max_depth:
            return []
        
        subtasks = []
        
        # 主要フェーズ
        phases = [
            "分析・計画",
            "リソース準備",
            "メイン実行",
            "検証・最適化"
        ]
        
        for i, phase in enumerate(phases):
            subtask = SubTask(
                task_id=f"task_{depth}_{i+1}",
                description=f"{phase}: {goal}",
                dependencies=[] if i == 0 else [f"task_{depth}_{i}"]
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _topological_sort(self, subtasks: List[SubTask]) -> List[str]:
        """依存関係に基づいた実行順序決定"""
        sorted_order = []
        completed = set()
        
        while len(sorted_order) < len(subtasks):
            for subtask in subtasks:
                if subtask.task_id in completed:
                    continue
                
                # 依存性確認
                if all(dep in completed for dep in subtask.dependencies):
                    sorted_order.append(subtask.task_id)
                    completed.add(subtask.task_id)
        
        return sorted_order


class ToolExecutor:
    """ツール実行エンジン"""
    
    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.SEMI_AUTONOMOUS):
        self.tools: Dict[str, Tool] = {}
        self.autonomy_level = autonomy_level
        self.execution_history: List[ToolResult] = []
        self.logger = logging.getLogger(__name__)
    
    def register_tool(self, tool: Tool) -> None:
        """ツール登録"""
        self.tools[tool.name] = tool
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any],
                    user_approval: Optional[bool] = None) -> ToolResult:
        """
        ツール実行
        
        Args:
            tool_name: ツール名
            params: 実行パラメータ
            user_approval: ユーザー承認フラグ
        
        Returns:
            ToolResult: 実行結果
        """
        if tool_name not in self.tools:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                error_message=f"Tool {tool_name} not found"
            )
        
        tool = self.tools[tool_name]
        
        # 承認判定
        if tool.require_approval and self.autonomy_level != AutonomyLevel.AUTONOMOUS:
            if user_approval is None:
                return ToolResult(
                    tool_name=tool_name,
                    status="pending_approval",
                    error_message="User approval required"
                )
            if not user_approval:
                return ToolResult(
                    tool_name=tool_name,
                    status="rejected",
                    error_message="User rejected execution"
                )
        
        # パラメータ検証
        missing_params = [p for p in tool.required_params if p not in params]
        if missing_params:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                error_message=f"Missing parameters: {missing_params}"
            )
        
        # 実行
        try:
            import time
            start_time = time.time()
            
            result = tool.execute_fn(**params)
            
            execution_time = time.time() - start_time
            
            tool_result = ToolResult(
                tool_name=tool_name,
                status="success",
                result=result,
                execution_time=execution_time
            )
        
        except Exception as e:
            tool_result = ToolResult(
                tool_name=tool_name,
                status="error",
                error_message=str(e)
            )
        
        self.execution_history.append(tool_result)
        return tool_result
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """ツール情報取得"""
        if tool_name not in self.tools:
            return None
        
        tool = self.tools[tool_name]
        return {
            "name": tool.name,
            "type": tool.tool_type.value,
            "description": tool.description,
            "required_params": tool.required_params,
            "optional_params": tool.optional_params
        }


class SelfImprovement:
    """自己改善・学習エンジン"""
    
    def __init__(self, memory_size: int = 1000):
        self.memory: List[Dict[str, Any]] = []
        self.memory_size = memory_size
        self.success_patterns: Dict[str, int] = {}
        self.failure_patterns: Dict[str, int] = {}
        self.learned_strategies: Dict[str, float] = {}
    
    def record_experience(self, task: str, action: str, result: bool,
                         execution_time: float, context: Dict) -> None:
        """
        実行経験を記録・分析
        
        Args:
            task: タスク説明
            action: 実施アクション
            result: 成功/失敗フラグ
            execution_time: 実行時間
            context: 実行コンテキスト
        """
        experience = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "action": action,
            "result": result,
            "execution_time": execution_time,
            "context": context
        }
        
        self.memory.append(experience)
        
        # メモリサイズ制限
        if len(self.memory) > self.memory_size:
            self.memory = self.memory[-self.memory_size:]
        
        # パターン分析
        if result:
            pattern_key = f"{task}:{action}"
            self.success_patterns[pattern_key] = \
                self.success_patterns.get(pattern_key, 0) + 1
        else:
            pattern_key = f"{task}:{action}"
            self.failure_patterns[pattern_key] = \
                self.failure_patterns.get(pattern_key, 0) + 1
    
    def get_success_rate(self) -> float:
        """成功率算出"""
        if not self.memory:
            return 0.0
        
        successes = sum(1 for exp in self.memory if exp["result"])
        return successes / len(self.memory)
    
    def recommend_strategy(self, task: str) -> Optional[str]:
        """
        学習データから推奨戦略を提案
        
        Args:
            task: タスク
        
        Returns:
            推奨アクション
        """
        best_action = None
        best_success_count = 0
        
        for pattern, count in self.success_patterns.items():
            if pattern.startswith(f"{task}:"):
                if count > best_success_count:
                    best_success_count = count
                    best_action = pattern.split(":", 1)[1]
        
        return best_action
    
    def get_learning_efficiency(self) -> float:
        """学習効率 (最近の成功率)"""
        recent_window = self.memory[-100:] if len(self.memory) > 100 else self.memory
        
        if not recent_window:
            return 0.0
        
        successes = sum(1 for exp in recent_window if exp["result"])
        return successes / len(recent_window)


class MonitoringSystem:
    """リアルタイムモニタリング・制御"""
    
    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
        self.constraints: Dict[str, Any] = {
            "max_execution_time": 3600,  # 1時間
            "max_retries": 3,
            "max_parallel_tasks": 5,
            "resource_limit_percent": 70
        }
        self.audit_log: List[Dict[str, Any]] = []
    
    def check_constraints(self, resource_usage: Dict[str, float]) -> Tuple[bool, List[str]]:
        """
        制約条件チェック
        
        Returns:
            (制約達成フラグ, 違反項目リスト)
        """
        violations = []
        
        if resource_usage.get("cpu_percent", 0) > self.constraints["resource_limit_percent"]:
            violations.append(f"CPU usage: {resource_usage['cpu_percent']}%")
        
        if resource_usage.get("memory_percent", 0) > self.constraints["resource_limit_percent"]:
            violations.append(f"Memory usage: {resource_usage['memory_percent']}%")
        
        return len(violations) == 0, violations
    
    def log_action(self, action_type: str, description: str, actor: str,
                   resource_impact: Dict[str, Any]) -> None:
        """監査ログ記録"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "description": description,
            "actor": actor,
            "resource_impact": resource_impact
        }
        self.audit_log.append(log_entry)
    
    def add_alert(self, severity: str, message: str, recommended_action: str) -> None:
        """アラート追加"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,  # "critical", "warning", "info"
            "message": message,
            "recommended_action": recommended_action
        }
        self.alerts.append(alert)


class AgentEngine:
    """統合エージェント実行エンジン"""
    
    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.SEMI_AUTONOMOUS):
        self.planner = TaskPlanner()
        self.executor = ToolExecutor(autonomy_level)
        self.self_improvement = SelfImprovement()
        self.monitoring = MonitoringSystem()
        self.autonomy_level = autonomy_level
        self.logger = logging.getLogger(__name__)
    
    def execute_goal(self, goal: str, context: Dict[str, Any],
                    user_approvals: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
        """
        ゴール達成の自律実行
        
        Args:
            goal: 達成ゴール
            context: 実行コンテキスト
            user_approvals: ユーザー承認マップ
        
        Returns:
            実行結果
        """
        # 1. タスク計画
        plan = self.planner.decompose_task(goal, context)
        self.logger.info(f"Plan created: {plan.estimated_steps} steps")
        
        # 2. 実行
        results = {}
        failed_tasks = []
        
        for task_id in plan.execution_order:
            subtask = next(t for t in plan.subtasks if t.task_id == task_id)
            
            subtask.status = TaskStatus.IN_PROGRESS
            
            # ツール実行
            tool_name = subtask.required_tools[0] if subtask.required_tools else None
            
            if tool_name:
                user_approval = user_approvals.get(task_id) if user_approvals else None
                result = self.executor.execute_tool(
                    tool_name,
                    {},
                    user_approval
                )
                
                if result.status == "success":
                    subtask.result = result.result
                    subtask.status = TaskStatus.COMPLETED
                    results[task_id] = result.result
                    
                    # 学習記録
                    self.self_improvement.record_experience(
                        task=goal,
                        action=tool_name,
                        result=True,
                        execution_time=result.execution_time,
                        context=context
                    )
                
                else:
                    failed_tasks.append(task_id)
                    subtask.status = TaskStatus.FAILED
                    
                    # 学習記録（失敗）
                    self.self_improvement.record_experience(
                        task=goal,
                        action=tool_name,
                        result=False,
                        execution_time=result.execution_time,
                        context=context
                    )
                    
                    # リトライ判定
                    if subtask.retry_count < subtask.max_retries:
                        subtask.retry_count += 1
                        subtask.status = TaskStatus.RETRYING
                        self.logger.warning(f"Retrying task {task_id}")
        
        # 3. 結果集約
        success = len(failed_tasks) == 0
        
        return {
            "goal": goal,
            "status": "completed" if success else "partial",
            "estimated_steps": plan.estimated_steps,
            "completed_steps": len(results),
            "results": results,
            "failed_tasks": failed_tasks,
            "success_rate": self.self_improvement.get_success_rate(),
            "execution_plan": {
                "total_subtasks": len(plan.subtasks),
                "execution_order": plan.execution_order
            }
        }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """エージェント状態取得"""
        return {
            "autonomy_level": self.autonomy_level.value,
            "success_rate": self.self_improvement.get_success_rate(),
            "learning_efficiency": self.self_improvement.get_learning_efficiency(),
            "memory_usage": len(self.self_improvement.memory),
            "total_experiences": len(self.self_improvement.memory),
            "alerts": len(self.monitoring.alerts),
            "audit_log_size": len(self.monitoring.audit_log)
        }
