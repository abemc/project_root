"""
ReAct Executor: 中央 Reasoning-Acting ループオーケストレータ

推論 → アクション → 観察 → 推論 を明示的に循環させ、
エージェントの自律実行を統制する中央制御機構。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging
import json

from .agent_engine import ExecutionPlan, SubTask, TaskStatus, Tool, ToolResult, AutonomyLevel
from ..reasoning_chain.reasoning_engine import ChainOfThoughtResult, ReasoningType

logger = logging.getLogger(__name__)


class ReActPhase(Enum):
    """ReAct サイクルのフェーズ"""
    THINK = "think"  # 推論: 状態を分析し、次のアクション計画
    ACT = "act"  # 行動: ツール実行
    OBSERVE = "observe"  # 観察: 結果を解釈
    REFLECT = "reflect"  # 反省: 目標達成度を再評価


@dataclass
class ReActStep:
    """ReAct サイクルの1ステップ"""
    step_number: int
    phase: ReActPhase
    content: str  # 推論/アクション/観察の内容
    reasoning: Optional[ChainOfThoughtResult] = None
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    tool_result: Optional[ToolResult] = None
    confidence: float = 0.0  # 0-1: この判断への信頼度
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActTrace:
    """ReAct 実行全体のトレース"""
    task_id: str
    goal: str
    steps: List[ReActStep] = field(default_factory=list)
    total_iterations: int = 0
    max_iterations: int = 10
    success: bool = False
    final_answer: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class ReActExecutor:
    """ReAct ループを実行・管理するエグゼキューター"""
    
    def __init__(
        self,
        reasoning_engine,  # ChainOfThoughtGenerator など
        tool_registry: Dict[str, Tool],
        autonomy_level: AutonomyLevel = AutonomyLevel.SEMI_AUTONOMOUS,
        max_iterations: int = 10,
        enable_logging: bool = True,
    ):
        """
        初期化
        
        Args:
            reasoning_engine: 推論実行エンジン（CoT/ToT など）
            tool_registry: {tool_name: Tool} の辞書
            autonomy_level: 自律レベル（ガードレール決定に使用）
            max_iterations: ReAct ループの最大反復回数
            enable_logging: トレース記録の有効化
        """
        self.reasoning_engine = reasoning_engine
        self.tool_registry = tool_registry
        self.autonomy_level = autonomy_level
        self.max_iterations = max_iterations
        self.enable_logging = enable_logging
        self.traces: List[ReActTrace] = []
    
    async def execute_task(
        self,
        task: SubTask,
        context: Dict[str, Any],
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> Tuple[bool, Any, ReActTrace]:
        """
        ReAct ループでタスクを実行
        
        Args:
            task: 実行対象タスク
            context: タスク実行コンテキスト（履歴、メモリアクセスなど）
            execution_plan: 全体計画（参照用）
        
        Returns:
            (成功フラグ, 最終結果, ReActTrace)
        """
        trace = ReActTrace(task_id=task.task_id, goal=task.description, max_iterations=self.max_iterations)
        step_num = 0
        
        logger.info(f"[ReAct] Task '{task.task_id}' 開始: {task.description}")
        
        while step_num < self.max_iterations:
            step_num += 1
            
            # Phase 1: THINK（推論）
            think_step = await self._phase_think(
                task, context, trace, step_num
            )
            trace.steps.append(think_step)
            
            # 推論結果から次のアクションを判定
            next_tool = await self._select_tool(think_step, task)
            if next_tool is None:
                # 推論結果が「終了」を示した
                logger.info(f"[ReAct] Task '{task.task_id}' 終了判定")
                trace.success = True
                trace.final_answer = think_step.content
                break
            
            # Phase 2: ACT（行動）
            act_step = await self._phase_act(
                task, next_tool, think_step, context, trace, step_num
            )
            trace.steps.append(act_step)
            
            # アクション失敗チェック
            if act_step.tool_result is None or act_step.tool_result.error:
                logger.warning(f"[ReAct] Tool '{next_tool.name}' 実行失敗")
                # 再推論へ（次のループで THINK フェーズ）
                continue
            
            # Phase 3: OBSERVE（観察）
            observe_step = await self._phase_observe(
                act_step, trace, step_num
            )
            trace.steps.append(observe_step)
            
            # Phase 4: REFLECT（反省）
            reflect_step = await self._phase_reflect(
                trace, step_num, execution_plan
            )
            trace.steps.append(reflect_step)
            
            # 目標達成判定
            if await self._is_goal_achieved(task, trace, context):
                logger.info(f"[ReAct] Task '{task.task_id}' 目標達成")
                trace.success = True
                break
        
        trace.total_iterations = step_num
        if self.enable_logging:
            self.traces.append(trace)
        
        # 最終結果の構築
        final_result = trace.final_answer or (
            trace.steps[-1].tool_result.output if trace.steps and trace.steps[-1].tool_result else None
        )
        
        return trace.success, final_result, trace
    
    async def _phase_think(
        self,
        task: SubTask,
        context: Dict[str, Any],
        trace: ReActTrace,
        step_num: int,
    ) -> ReActStep:
        """THINK フェーズ: 推論実行"""
        logger.debug(f"[ReAct:THINK] Step {step_num}")
        
        # CoT ロジック：現在の状態を分析し、次のステップを計画
        prompt = f"""
Task: {task.description}
Context: {json.dumps(context, indent=2, default=str)[:500]}
Previous steps: {len(trace.steps)}

What should be the next action? Analyze step-by-step.
"""
        
        reasoning_result = await self.reasoning_engine.generate_chain(
            prompt,
            max_steps=5
        )
        
        think_step = ReActStep(
            step_number=step_num,
            phase=ReActPhase.THINK,
            content=reasoning_result.final_answer or reasoning_result.reasoning_trace,
            reasoning=reasoning_result,
            confidence=reasoning_result.confidence_score,
        )
        
        return think_step
    
    async def _select_tool(self, think_step: ReActStep, task: SubTask) -> Optional[Tool]:
        """推論結果からツール選択"""
        # 簡易実装: 推論テキストに "complete" が含まれていたら終了
        if "complete" in think_step.content.lower() or "done" in think_step.content.lower():
            return None
        
        # それ以外は required_tools の中から最初のツールを選択
        if task.required_tools:
            tool_name = task.required_tools[0]
            return self.tool_registry.get(tool_name)
        
        return None
    
    async def _phase_act(
        self,
        task: SubTask,
        tool: Tool,
        think_step: ReActStep,
        context: Dict[str, Any],
        trace: ReActTrace,
        step_num: int,
    ) -> ReActStep:
        """ACT フェーズ: ツール実行"""
        logger.debug(f"[ReAct:ACT] Step {step_num}, Tool: {tool.name}")
        
        # ガードレール: 承認が必要なツールをチェック
        if tool.require_approval and self.autonomy_level == AutonomyLevel.SUPERVISED:
            logger.warning(f"[ReAct] Tool '{tool.name}' requires approval (autonomy level: SUPERVISED)")
            # 実装: ここでユーザー確認ダイアログを呼び出すことも可能
        
        # ツール実行
        tool_params = context.get("tool_params", {})
        tool_result = None
        error = None
        
        try:
            tool_result = await tool.execute_fn(**tool_params)
        except Exception as e:
            error = str(e)
            logger.error(f"[ReAct] Tool '{tool.name}' error: {error}")
        
        act_step = ReActStep(
            step_number=step_num,
            phase=ReActPhase.ACT,
            content=f"Execute tool '{tool.name}'",
            tool_name=tool.name,
            tool_params=tool_params,
            tool_result=tool_result,
            confidence=0.9 if not error else 0.1,
            metadata={"error": error} if error else {},
        )
        
        return act_step
    
    async def _phase_observe(
        self,
        act_step: ReActStep,
        trace: ReActTrace,
        step_num: int,
    ) -> ReActStep:
        """OBSERVE フェーズ: 結果の観察・解釈"""
        logger.debug(f"[ReAct:OBSERVE] Step {step_num}")
        
        result_summary = ""
        if act_step.tool_result:
            result_summary = f"Output: {str(act_step.tool_result.output)[:200]}"
        
        observe_step = ReActStep(
            step_number=step_num,
            phase=ReActPhase.OBSERVE,
            content=f"Observed result from {act_step.tool_name}: {result_summary}",
            confidence=0.85,
        )
        
        return observe_step
    
    async def _phase_reflect(
        self,
        trace: ReActTrace,
        step_num: int,
        execution_plan: Optional[ExecutionPlan],
    ) -> ReActStep:
        """REFLECT フェーズ: 進捗・戦略の再評価"""
        logger.debug(f"[ReAct:REFLECT] Step {step_num}")
        
        # 進捗状況の評価
        progress = f"Steps completed: {step_num}/{trace.max_iterations}"
        
        reflect_step = ReActStep(
            step_number=step_num,
            phase=ReActPhase.REFLECT,
            content=f"Progress check: {progress}. Strategy remains valid.",
            confidence=0.8,
            metadata={"progress": progress},
        )
        
        return reflect_step
    
    async def _is_goal_achieved(
        self,
        task: SubTask,
        trace: ReActTrace,
        context: Dict[str, Any],
    ) -> bool:
        """目標達成判定"""
        # 簡易実装: 最後のステップが成功していれば OK
        if trace.steps:
            last_step = trace.steps[-1]
            return last_step.phase == ReActPhase.REFLECT and last_step.confidence > 0.7
        return False
    
    def get_trace(self, task_id: str) -> Optional[ReActTrace]:
        """タスク ID からトレースを取得"""
        for trace in self.traces:
            if trace.task_id == task_id:
                return trace
        return None
    
    def export_traces_jsonl(self, file_path: str):
        """トレースを JSONL で出力"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for trace in self.traces:
                    trace_dict = {
                        'task_id': trace.task_id,
                        'goal': trace.goal,
                        'total_iterations': trace.total_iterations,
                        'success': trace.success,
                        'final_answer': trace.final_answer,
                        'created_at': trace.created_at.isoformat(),
                        'steps': [
                            {
                                'step_number': s.step_number,
                                'phase': s.phase.value,
                                'content': s.content,
                                'tool_name': s.tool_name,
                                'confidence': s.confidence,
                            }
                            for s in trace.steps
                        ],
                    }
                    f.write(json.dumps(trace_dict, ensure_ascii=False) + '\n')
            logger.info(f"Traces exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export traces: {e}")
