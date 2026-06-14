"""
Phase 1 統合テスト: ReAct + メモリ + 監査

新しく実装した自立型AI機能の統合テスト
"""

import pytest
import asyncio
import tempfile
import json
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.agent_architecture.react_executor import ReActExecutor, ReActTrace, ReActStep, ReActPhase
from src.memory.episodic_memory import EpisodicMemory
from src.memory.rag_integrator import RAGIntegrator
from src.audit.audit_logger import AuditLogger, AuditEventType
from src.reasoning_chain.reasoning_engine import ChainOfThoughtResult, ThoughtStep, ReasoningType
from src.agent_architecture.agent_engine import SubTask, Tool, ToolResult, TaskStatus, AutonomyLevel


# ===========================================================================
# モック定義
# ===========================================================================

class MockEmbeddingModel:
    """埋め込みモデルのモック"""
    def embed(self, text: str):
        # 384次元の簡易的なベクトルを返す
        return [0.1] * 384


class MockEmbedStore:
    """FAISSストアのモック"""
    def __init__(self):
        self.vectors = []
        self.metadatas = []

    def add_vector(self, vector, metadata):
        self.vectors.append(vector)
        self.metadatas.append(metadata)

    def search(self, vector, top_k=5):
        results = []
        # すべてのベクトルに対してダミーの類似度1.0を返却
        for i, meta in enumerate(self.metadatas):
            results.append({
                'metadata': meta,
                'similarity': 1.0 - (0.01 * i)
            })
        return results[:top_k]


# ===========================================================================
# テストクラス
# ===========================================================================

class TestReActExecutor:
    """ReAct Executor のテスト"""

    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        # 1. モックのセットアップ
        mock_cot_result_1 = ChainOfThoughtResult(
            question="Analyze task",
            steps=[
                ThoughtStep(step_number=1, content="Thinking about target", reasoning_type=ReasoningType.CHAIN_OF_THOUGHT, confidence=0.9)
            ],
            final_answer="I will use the test tool to proceed.",
            reasoning_trace="Step 1: Thinking",
            confidence_score=0.9
        )
        mock_cot_result_2 = ChainOfThoughtResult(
            question="Analyze task",
            steps=[
                ThoughtStep(step_number=2, content="Verify result", reasoning_type=ReasoningType.CHAIN_OF_THOUGHT, confidence=0.9)
            ],
            final_answer="Formulating final answer: done",
            reasoning_trace="Step 2: Verification",
            confidence_score=0.9
        )
        
        mock_reasoning_engine = Mock()
        mock_reasoning_engine.generate_chain = AsyncMock(side_effect=[mock_cot_result_1, mock_cot_result_2])

        # 模擬ツールの定義
        mock_tool_fn = AsyncMock(return_value=ToolResult(
            tool_name="test_tool",
            status="success",
            result="Tool Output Success",
            execution_time=0.1
        ))
        
        tool = Tool(
            name="test_tool",
            tool_type=ReasoningType.CHAIN_OF_THOUGHT, # ここでは型を適当に合わせる
            description="Mock tool description",
            execute_fn=mock_tool_fn,
            required_params=["query"]
        )
        
        tool_registry = {"test_tool": tool}

        # 2. テスト対象の初期化
        executor = ReActExecutor(
            reasoning_engine=mock_reasoning_engine,
            tool_registry=tool_registry,
            autonomy_level=AutonomyLevel.SEMI_AUTONOMOUS,
            max_iterations=3
        )

        task = SubTask(
            task_id="task_react_test",
            description="Identify the target details",
            required_tools=["test_tool"]
        )

        context = {"tool_params": {"query": "hello"}}

        # 3. 実行
        success, final_result, trace = await executor.execute_task(task, context)

        # 4. アサーション
        assert success is True
        assert "done" in final_result.lower() or "success" in final_result.lower()
        assert len(trace.steps) > 0
        assert trace.steps[0].phase == ReActPhase.THINK
        assert trace.steps[1].phase == ReActPhase.ACT


class TestRAGIntegrator:
    """RAG Integrator のテスト"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # 一時ディレクトリ作成
        self.test_dir = Path(tempfile.mkdtemp())
        self.episodic_memory = EpisodicMemory(storage_dir=self.test_dir)
        self.mock_embed_store = MockEmbedStore()
        self.mock_embed_model = MockEmbeddingModel()
        
        self.integrator = RAGIntegrator(
            episodic_memory=self.episodic_memory,
            embed_store=self.mock_embed_store,
            embedding_model=self.mock_embed_model,
            auto_index=True
        )
        yield
        # テストクリーンアップ
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_store_and_auto_index_episode(self):
        episode = {
            "trigger": "User search",
            "query": "Who is high president?",
            "action": "web_search",
            "result": "Information about high president",
            "resolution": "Resolved details",
            "confidence": 0.8
        }

        # エピソード保存＆自動インデックス
        episode_id = self.integrator.integrate_episode(episode)
        
        assert episode_id is not None
        assert len(self.episodic_memory.episodes) == 1
        assert self.mock_embed_store.metadatas[0]['episode_id'] == episode_id
        
        # 統計情報検証
        stats = self.integrator.get_stats()
        assert stats['total_episodes'] == 1
        assert stats['indexed_episodes'] == 1

    def test_search_semantic_and_hybrid(self):
        ep1 = {"trigger": "trigger1", "query": "Apple weather", "action": "search", "result": "sunny", "confidence": 0.9}
        ep2 = {"trigger": "trigger2", "query": "Banana banana", "action": "search", "result": "rainy", "confidence": 0.8}

        self.integrator.integrate_episode(ep1)
        self.integrator.integrate_episode(ep2)

        # セマンティック検索
        semantic_results = self.integrator.search_episodes_by_semantic("weather", top_k=1)
        assert len(semantic_results) > 0
        
        # ハイブリッド検索
        hybrid_results = self.integrator.search_hybrid("Apple", top_k=2)
        assert len(hybrid_results) > 0

    def test_garbage_collection(self):
        # 古いエピソードや低信頼度エピソードの登録
        ep_old = {
            "query": "Old task query",
            "confidence": 0.1,  # 閾値 0.3 未満
            "timestamp": "2020-01-01T00:00:00"
        }
        ep_ok = {
            "query": "Ok task query",
            "confidence": 0.9,
            "timestamp": datetime.now().isoformat()
        }

        self.integrator.integrate_episode(ep_old)
        self.integrator.integrate_episode(ep_ok)

        assert len(self.episodic_memory.episodes) == 2

        # GC実行
        deleted = self.integrator.garbage_collect(min_confidence=0.3, max_age_days=30)
        
        assert deleted == 1
        assert len(self.episodic_memory.episodes) == 1
        assert self.episodic_memory.episodes[0]['query'] == "Ok task query"


class TestAuditLogger:
    """監査ロガーのテスト"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(log_dir=self.test_dir, agent_id="test_agent", enable_console=False)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_log_task_and_retrieve_trail(self):
        task_id = "task_audit_001"
        
        # イベント記録
        self.audit_logger.log_task_start(task_id, "Analyze system", "semi_autonomous")
        self.audit_logger.log_thinking_step(task_id, 1, "Analyzing rules...", 0.9)
        self.audit_logger.log_tool_selected(task_id, "verifier", "Needed to verify result")
        self.audit_logger.log_tool_execution(task_id, "verifier", {"expr": "1+1"}, True, "2", None, 0.05)
        self.audit_logger.log_task_end(task_id, True, "Completed analyzer execution", 1.2)

        # 監査証跡の取得
        trail = self.audit_logger.get_task_audit_trail(task_id)
        assert len(trail) == 5
        assert trail[0]['event_type'] == "task_start"
        assert trail[1]['event_type'] == "thinking_step"
        assert trail[2]['event_type'] == "tool_selected"
        assert trail[3]['event_type'] == "tool_execution_end"
        assert trail[4]['event_type'] == "task_end"

        # サマリーのエクスポート
        summary = self.audit_logger.export_summary()
        assert summary['summary']['total_events'] == 5
        assert summary['summary']['tool_executions'] == 1


class TestPhase1Integration:
    """Phase 1 全体統合テスト (E2E シナリオ)"""

    @pytest.mark.asyncio
    async def test_react_memory_audit_integration_workflow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 各コンポーネントの初期化
            episodic_memory = EpisodicMemory(storage_dir=temp_path)
            mock_embed_store = MockEmbedStore()
            mock_embed_model = MockEmbeddingModel()
            
            integrator = RAGIntegrator(
                episodic_memory=episodic_memory,
                embed_store=mock_embed_store,
                embedding_model=mock_embed_model,
                auto_index=True
            )

            audit_logger = AuditLogger(log_dir=temp_dir, agent_id="integrated_agent", enable_console=False)

            # ReAct 用モック Reasoning Engine
            mock_cot_result_1 = ChainOfThoughtResult(
                question="Execute integrated task",
                steps=[
                    ThoughtStep(step_number=1, content="Using RAG integration to resolve query", reasoning_type=ReasoningType.CHAIN_OF_THOUGHT, confidence=0.95)
                ],
                final_answer="I will use the integration_tool to proceed.",
                reasoning_trace="CoT Step 1: Run integration",
                confidence_score=0.95
            )
            mock_cot_result_2 = ChainOfThoughtResult(
                question="Execute integrated task",
                steps=[
                    ThoughtStep(step_number=2, content="Verify integration", reasoning_type=ReasoningType.CHAIN_OF_THOUGHT, confidence=0.95)
                ],
                final_answer="Integration done successfully",
                reasoning_trace="CoT Step 2: Verified",
                confidence_score=0.95
            )
            mock_reasoning_engine = Mock()
            mock_reasoning_engine.generate_chain = AsyncMock(side_effect=[mock_cot_result_1, mock_cot_result_2])

            # ツールの挙動定義: 実行時に RAGIntegrator を通してエピソード記憶を自動追加・更新する
            async def mock_integration_tool_fn(**kwargs):
                # ツールが実行されたら、その記憶を RAGIntegrator に統合
                episode = {
                    "trigger": "react_flow",
                    "query": "integrated query",
                    "action": "integration_tool",
                    "result": "success",
                    "resolution": "Integration verified",
                    "confidence": 0.9
                }
                integrator.integrate_episode(episode)
                return ToolResult(
                    tool_name="integration_tool",
                    status="success",
                    result="Memory Stored Success",
                    execution_time=0.2
                )

            tool = Tool(
                name="integration_tool",
                tool_type=ReasoningType.CHAIN_OF_THOUGHT,
                description="Mock integration tool",
                execute_fn=mock_integration_tool_fn,
                required_params=[]
            )

            tool_registry = {"integration_tool": tool}

            executor = ReActExecutor(
                reasoning_engine=mock_reasoning_engine,
                tool_registry=tool_registry,
                autonomy_level=AutonomyLevel.SEMI_AUTONOMOUS,
                max_iterations=3,
                audit_logger=audit_logger
            )

            task = SubTask(
                task_id="task_e2e_integration_001",
                description="Perform e2e integration flow",
                required_tools=["integration_tool"]
            )

            # 実行
            success, final_result, trace = await executor.execute_task(task, context={})

            # アサーション
            assert success is True
            assert "success" in final_result.lower() or "done" in final_result.lower()
            
            # メモリが自動インデックス化されたか検証
            stats = integrator.get_stats()
            assert stats['total_episodes'] == 1
            assert stats['indexed_episodes'] == 1
            
            # 監査証跡が完全であるか検証
            audit_trail = audit_logger.get_task_audit_trail("task_e2e_integration_001")
            assert len(audit_trail) >= 4
            event_types = [entry['event_type'] for entry in audit_trail]
            assert "task_start" in event_types
            assert "thinking_step" in event_types
            assert "tool_execution_end" in event_types
            assert "task_end" in event_types
