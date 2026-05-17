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
import os


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
        # If rag_docs present in context, use them to influence complexity and subtasks
        complexity = self._analyze_complexity(goal)
        try:
            rag_docs = context.get('rag_docs') if isinstance(context, dict) else None
        except Exception:
            rag_docs = None

        if rag_docs:
            try:
                doc_count = len(rag_docs)
                if doc_count >= 3:
                    complexity = "complex"
                # use TF-IDF extractor and summarizer from rag_utils
                try:
                    from .rag_utils import extract_keywords_tfidf, summarize_docs
                    keywords = extract_keywords_tfidf(rag_docs, top_k=8)
                    summary_text = summarize_docs(rag_docs, max_sentences=2, keywords=keywords)
                except Exception:
                    keywords = self._extract_keywords_from_rag(rag_docs, top_k=5)
                    summary_text = ''
            except Exception:
                keywords = []
                summary_text = ''
        else:
            keywords = []
            summary_text = ''
        
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
            # If rag-derived keywords exist, prepend synthesis and summary subtasks
            if keywords:
                synth_desc = f"synthesize context: {', '.join(keywords)}"
                if summary_text:
                    synth_desc += f" — summary: {summary_text[:160]}"
                synth = SubTask(task_id="task_synth", description=synth_desc, required_tools=["summarizer"])
                summary = SubTask(task_id="task_summary", description="summarize synthesized findings", required_tools=["summarizer"]) 
                # ensure synthesis runs before existing subtasks
                subtasks = [synth, summary] + subtasks
                # wire dependencies: existing subtasks depend on summary
                for s in subtasks[2:]:
                    if s.task_id:
                        s.dependencies = s.dependencies or []
                        if "task_summary" not in s.dependencies:
                            s.dependencies.append("task_summary")
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

        # Use RAG docs in context to suggest additional tools or escalate complexity
        try:
            rag_docs = context.get('rag_docs') if isinstance(context, dict) else None
            if rag_docs:
                # look for tags or meta hints
                for d in rag_docs:
                    tags = d.get('meta', {}).get('tags', []) if isinstance(d.get('meta'), dict) else []
                    for t in tags:
                        tk = str(t).lower()
                        if 'test' in tk or 'qa' in tk:
                            if 'verifier' not in required_tools:
                                required_tools.append('verifier')
                        if 'analysis' in tk or '数学' in tk or '解析' in tk:
                            if 'calculator' not in required_tools:
                                required_tools.append('calculator')
                        if 'example' in tk or '使い方' in tk:
                            if 'web_search' not in required_tools:
                                required_tools.append('web_search')
        except Exception:
            pass
        
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

    def _extract_keywords_from_rag(self, docs: List[Dict], top_k: int = 5) -> List[str]:
        """Very simple keyword extraction from rag docs: token frequency excluding short tokens."""
        try:
            from collections import Counter
            import re
            cnt = Counter()
            stopwords = set(["the", "and", "for", "with", "this", "that", "に", "の", "を", "は", "が", "で", "です", "ます"])
            for d in docs:
                text = d.get('text') or ''
                tokens = re.findall(r"\w{2,}", text, flags=re.UNICODE)
                for t in tokens:
                    tt = t.strip().lower()
                    if len(tt) >= 2 and tt not in stopwords:
                        cnt[tt] += 1
            most = [w for w, _ in cnt.most_common(top_k)]
            return most
        except Exception:
            return []

    def _create_subtasks_from_keywords(self, keywords: List[str]) -> List[SubTask]:
        """Map extracted keywords to domain subtasks."""
        subtasks: List[SubTask] = []
        seen = set()
        def add_task(tid, desc, tools):
            base = tid
            i = 1
            while any(s.task_id == tid for s in subtasks):
                i += 1
                tid = f"{base}_{i}"
            subtasks.append(SubTask(task_id=tid, description=desc, required_tools=tools))

        kws = set([k.lower() for k in keywords])
        if any(k in kws for k in ("design", "設計", "plan", "planing")):
            add_task("task_create_spec", "create design specification from retrieved docs", ["file_writer"])
        if any(k in kws for k in ("example", "usage", "使い方", "サンプル")):
            add_task("task_examples", "generate usage examples and snippets", ["summarizer"])
        if any(k in kws for k in ("test", "テスト", "qa", "verify")):
            add_task("task_tests", "create verification tests or checks", ["verifier"])
        if any(k in kws for k in ("optimize", "最適化", "performance")):
            add_task("task_optimize", "identify optimization opportunities", ["web_search"]) 

        return subtasks


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
            import inspect
            start_time = time.time()

            # Filter params to only those accepted by the callable to avoid unexpected kwargs
            try:
                sig = inspect.signature(tool.execute_fn)
                accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if accepts_kwargs:
                    filtered_params = params
                else:
                    accepted = set(sig.parameters.keys())
                    filtered_params = {k: v for k, v in params.items() if k in accepted}
            except Exception:
                filtered_params = params

            result = tool.execute_fn(**filtered_params)
            
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
        self._experience_count = 0
        self.logger = logging.getLogger(__name__)
        # Attempt to load a RAG FaissStore if present
        try:
            from src.rag.embed_store import FaissStore
            idx_path = os.path.join('corpus', 'rag_store.index')
            meta_path = os.path.join('corpus', 'rag_store_meta.json')
            if os.path.exists(idx_path):
                self.rag_store = FaissStore(index_path=idx_path, meta_path=meta_path)
            else:
                self.rag_store = None
        except Exception:
            self.rag_store = None
    
    def execute_goal(self, goal: str, context: Dict[str, Any],
                    user_approvals: Optional[Dict[str, bool]] = None,
                    use_dynamic_manager: bool = False) -> Dict[str, Any]:
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
        # If RAG store available, run a quick retrieval for the goal and pass docs into planning context
        try:
            if getattr(self, 'rag_store', None) is not None:
                qv = self.rag_store.embed_fn(goal or '')
                docs = self.rag_store.search(qv, top_k=5)
                context = dict(context or {})
                context['rag_docs'] = docs
        except Exception:
            pass

        plan = self.planner.decompose_task(goal, context)
        self.logger.info(f"Plan created: {plan.estimated_steps} steps")

        # If requested, hand off execution to DynamicTaskManager for dynamic scheduling
        if use_dynamic_manager:
            try:
                from .dynamic_task_manager import DynamicTaskManager

                dtm = DynamicTaskManager(planner=self.planner, executor=self.executor, monitor=self.monitoring)
                summary = dtm.execute_plan(plan, user_approvals=user_approvals)
                # enrich summary with goal and estimated steps
                summary.setdefault("goal", goal)
                summary.setdefault("estimated_steps", plan.estimated_steps)
                if "execution_plan" not in summary:
                    summary["execution_plan"] = {"execution_order": plan.execution_order}
                return summary
            except Exception as exc:
                self.logger.warning(f"DynamicTaskManager unavailable or failed: {exc}")

        # 2. 実行（既存の逐次実行パス）
        results = {}
        failed_tasks = []

        for task_id in plan.execution_order:
            subtask = next(t for t in plan.subtasks if t.task_id == task_id)

            subtask.status = TaskStatus.IN_PROGRESS

            # ツール実行
            tool_name = subtask.required_tools[0] if subtask.required_tools else None

            # If RAG store available, retrieve relevant docs for this subtask and pass to tool
            retrieved = None
            try:
                if getattr(self, 'rag_store', None) is not None:
                    qv = self.rag_store.embed_fn(subtask.description or '')
                    retrieved = self.rag_store.search(qv, top_k=5)
            except Exception:
                retrieved = None

            if tool_name:
                user_approval = user_approvals.get(task_id) if user_approvals else None
                params = {"query": subtask.description, "docs": retrieved}
                result = self.executor.execute_tool(
                    tool_name,
                    params,
                )

                if isinstance(result, ToolResult):
                    results[task_id] = result
                else:
                    results[task_id] = ToolResult(tool_name=tool_name, status="success", result=result)

                if getattr(results[task_id], "status", "success") != "success":
                    failed_tasks.append(task_id)
            else:
                results[task_id] = ToolResult(tool_name=None, status="skipped", result=None)

            # Record experience into SelfImprovement (best-effort)
            try:
                status_val = getattr(results[task_id], "status", "skipped")
                success_flag = True if status_val == "success" else False
                action = tool_name or "no_tool"
                # record with minimal execution_time and context
                if self.self_improvement:
                    self.self_improvement.record_experience(
                        task=getattr(subtask, "description", task_id) or task_id,
                        action=action,
                        result=success_flag,
                        execution_time=0.0,
                        context={}
                    )
                    try:
                        self._experience_count += 1
                    except Exception:
                        pass
            except Exception:
                pass

        summary = {
            "goal": goal,
            "status": "completed" if not failed_tasks else "partial_failure",
            "estimated_steps": plan.estimated_steps,
            "completed_steps": len([r for r in results.values() if getattr(r, "status", "success") == "success"]),
            "results": results,
            "failed_tasks": failed_tasks,
            "execution_plan": {
                "execution_order": plan.execution_order
            }
        }
        return summary

    def get_agent_status(self) -> Dict[str, Any]:
        """シンプルなエージェント状態ダンプ（テスト用）"""
        status = {
            "autonomy_level": self.autonomy_level.value if hasattr(self.autonomy_level, 'value') else str(self.autonomy_level),
            "success_rate": 0.0,
            "learning_efficiency": 0.0,
            "memory_usage": 0,
            "total_experiences": 0,
        }

        try:
            status["success_rate"] = float(self.self_improvement.get_success_rate())
            status["learning_efficiency"] = float(self.self_improvement.get_learning_efficiency())
            total = len(getattr(self.self_improvement, "memory", []))
            # fallback to internal counter if memory appears empty due to test ordering
            if total == 0:
                total = int(getattr(self, "_experience_count", 0))
            status["total_experiences"] = total
            status["memory_usage"] = status["total_experiences"]
        except Exception:
            # best-effort; keep defaults
            pass

        return status
