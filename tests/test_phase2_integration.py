"""
Phase 2 統合テスト: フィードバック + エラー学習 + パターン抽出

フィードバック処理、エラー学習、パターン抽出の統合動作確認
"""

import pytest
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from src.feedback.feedback_handler import FeedbackHandler, FeedbackType, FeedbackSeverity
from src.self_improvement.error_learning import ErrorLearner, ErrorCategory
from src.learning.pattern_extractor import PatternExtractor, PatternType
from src.agent_architecture.react_executor import ReActExecutor
from src.agent_architecture.agent_engine import SubTask, Tool, ToolResult, AutonomyLevel
from src.reasoning_chain.reasoning_engine import ChainOfThoughtResult, ThoughtStep, ReasoningType
from unittest.mock import AsyncMock, Mock


class TestFeedbackHandler:
    """フィードバックハンドラーのテスト"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        self.handler = FeedbackHandler(storage_dir=self.test_dir, auto_apply=True, pattern_threshold=2)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_record_and_apply_feedback(self):
        # フィードバック記録
        task_id = "task_001"
        self.handler.record_feedback(
            task_id=task_id,
            feedback_type=FeedbackType.TOOL_CORRECTION,
            severity=FeedbackSeverity.HIGH,
            content="Use smart web search",
            affected_component="web_search",
            suggested_action="smart_web_search"
        )

        assert len(self.handler.feedbacks) == 1
        assert self.handler.feedbacks[0].task_id == task_id
        assert self.handler.feedbacks[0].applied is False

        # 計画に適用
        plan = {
            "main_goal": "Search the latest LLM trends",
            "subtasks": []
        }
        modified_plan = self.handler.apply_feedback_to_plan(plan, task_id=task_id)

        assert "feedback_applied" in modified_plan
        assert len(modified_plan["feedback_applied"]) == 1
        assert modified_plan["feedback_applied"][0]["type"] == "tool_correction"
        assert modified_plan["feedback_applied"][0]["suggestion"] == "smart_web_search"
        assert self.handler.feedbacks[0].applied is True


class TestErrorLearner:
    """エラー学習のテスト"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        self.learner = ErrorLearner(storage_dir=self.test_dir, pattern_threshold=2)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_record_and_get_recovery_suggestions(self):
        task_id = "task_error_001"
        # 1回目のエラー
        self.learner.record_error(
            task_id=task_id,
            tool_name="web_search",
            error_category=ErrorCategory.TIMEOUT,
            error_message="Connection timeout during fetch"
        )
        # 2回目のエラー (パターン認定のための閾値 2 を満たすため)
        err_id2 = self.learner.record_error(
            task_id=task_id,
            tool_name="web_search",
            error_category=ErrorCategory.TIMEOUT,
            error_message="Connection timeout during fetch"
        )

        # 2回目のエラーを解決済みとし、解決方法を学習させる
        self.learner.resolve_error(err_id2, "Use offline backup corpus cache")

        # 類似エラーに対する提案を取得
        suggestions = self.learner.get_recovery_suggestions(
            error_message="Connection timeout during fetch",
            tool_name="web_search"
        )

        assert len(suggestions) >= 1
        assert "Use offline backup corpus cache" in suggestions


class TestPatternExtractor:
    """パターン抽出のテスト"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        self.extractor = PatternExtractor(storage_dir=self.test_dir, pattern_threshold=2, min_success_rate=0.5)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pattern_recommendation(self):
        # 成功した同一パターンのトレースを 2件 (閾値) 登録
        for i in range(2):
            self.extractor.record_trace(
                task_id=f"task_pattern_{i}",
                tool_sequence=["fetch_doc", "extract_meta"],
                parameters_used={"fetch_doc": {"timeout": 10}},
                context={"file_size_kb": 120.0},
                success=True,
                duration_seconds=1.5
            )

        assert len(self.extractor.traces) == 2
        assert len(self.extractor.patterns) >= 2  # TOOL_SEQUENCE, PARAMETER_SET, CONTEXT_CONDITION

        # 推奨アクションの取得
        recommendations = self.extractor.get_recommended_actions(
            context={"file_size_kb": 120.0},
            current_tools=["fetch_doc", "extract_meta"]
        )

        assert recommendations["tool_sequence"] == ["fetch_doc", "extract_meta"]
        assert recommendations["confidence"] > 0.0


class TestPhase2Integration:
    """Phase 2 全体統合テスト"""

    def test_feedback_error_pattern_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = FeedbackHandler(storage_dir=temp_dir, pattern_threshold=2)
            learner = ErrorLearner(storage_dir=temp_dir, pattern_threshold=2)
            extractor = PatternExtractor(storage_dir=temp_dir, pattern_threshold=2)

            # 1. 成功パターンのトレース登録
            for i in range(2):
                extractor.record_trace(
                    task_id=f"task_flow_{i}",
                    tool_sequence=["qa_search", "summarize"],
                    parameters_used={},
                    context={},
                    success=True,
                    duration_seconds=0.8
                )
            
            # パターンが抽出されたか検証
            assert len(extractor.patterns) > 0

            # 2. エラー記録と解決
            err_id1 = learner.record_error("task_flow_2", "summarize", ErrorCategory.TOOL_FAILURE, "Out of memory")
            err_id2 = learner.record_error("task_flow_3", "summarize", ErrorCategory.TOOL_FAILURE, "Out of memory")
            learner.resolve_error(err_id2, "Truncate document to 1000 characters first")

            suggestions = learner.get_recovery_suggestions("Out of memory", "summarize")
            assert "Truncate document to 1000 characters first" in suggestions

            # 3. ユーザーからの修正フィードバック登録
            handler.record_feedback(
                task_id="task_flow_4",
                feedback_type=FeedbackType.STRATEGY_CHANGE,
                severity=FeedbackSeverity.MEDIUM,
                content="Summarize early",
                affected_component="summarizer"
            )
            
            # 計画に適用
            plan = {"main_goal": "Flow goal", "subtasks": []}
            modified_plan = handler.apply_feedback_to_plan(plan, "task_flow_4")
            assert "feedback_applied" in modified_plan

    @pytest.mark.asyncio
    async def test_react_executor_feedback_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = FeedbackHandler(storage_dir=temp_dir, auto_apply=True)
            
            task_id = "task_integrated_001"
            
            # フィードバック記録 (元のツールは original_tool だが、修正後は corrected_tool に修正すべき)
            handler.record_feedback(
                task_id=task_id,
                feedback_type=FeedbackType.TOOL_CORRECTION,
                severity=FeedbackSeverity.HIGH,
                content="Use corrected tool instead of original",
                affected_component="tool_selection",
                suggested_action="corrected_tool"
            )

            # ツールの定義
            async def mock_corrected_tool_fn(**kwargs):
                return ToolResult(
                    tool_name="corrected_tool",
                    status="success",
                    result="Corrected Tool Executed Successfully"
                )

            corrected_tool = Tool(
                name="corrected_tool",
                tool_type=ReasoningType.CHAIN_OF_THOUGHT,
                description="Corrected tool execution",
                execute_fn=mock_corrected_tool_fn,
                required_params=[]
            )

            tool_registry = {"corrected_tool": corrected_tool}

            # モックの推論エンジン
            mock_cot_result = ChainOfThoughtResult(
                question="Execute task",
                steps=[
                    ThoughtStep(step_number=1, content="Use corrected_tool to complete", reasoning_type=ReasoningType.CHAIN_OF_THOUGHT, confidence=0.9)
                ],
                final_answer="Integration done successfully",
                reasoning_trace="CoT Step 1: Run integration",
                confidence_score=0.95
            )
            mock_reasoning_engine = Mock()
            mock_reasoning_engine.generate_chain = AsyncMock(return_value=mock_cot_result)

            executor = ReActExecutor(
                reasoning_engine=mock_reasoning_engine,
                tool_registry=tool_registry,
                autonomy_level=AutonomyLevel.SEMI_AUTONOMOUS,
                max_iterations=2,
                feedback_handler=handler
            )

            task = SubTask(
                task_id=task_id,
                description="Perform integrated task flow",
                required_tools=["original_tool"]  # 最初は original_tool を要求
            )

            # 実行
            success, final_result, trace = await executor.execute_task(task, context={})

            # アサーション: 実行が成功し、corrected_tool の結果が得られていること
            assert success is True
            assert "corrected" in final_result.lower() or "success" in final_result.lower()
            
            # タスク要求ツールが corrected_tool に書き換わっていること
            assert task.required_tools == ["corrected_tool"]

            # フィードバックが適用済みにマークされていること
            assert handler.feedbacks[0].applied is True
