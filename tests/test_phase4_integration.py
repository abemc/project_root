"""
Phase 4 Integration Tests: 実行環境

ToolExecutor, EventLoop, FallbackChain が正しく統合されて動作することを確認。
Permission, Explainability, Ethics, Sandbox との連携も検証。
"""

import pytest
from datetime import datetime
from typing import Dict

# Phase 4 imports
from src.execution.tool_executor import (
    ToolExecutor,
    ToolDefinition,
    ToolRegistry,
    ToolType,
    ExecutionPhase,
)
from src.execution.event_loop import (
    EventLoop,
    Task,
    TaskPriority,
    TaskStatus,
    EventType,
    TaskGraph,
)
from src.execution.fallback_chain import (
    FallbackChain,
    FallbackStrategy,
)


class TestToolExecutorIntegration:
    """ToolExecutor 統合テスト"""
    
    @pytest.fixture
    def executor(self):
        return ToolExecutor()
    
    def test_tool_registry_contains_defaults(self, executor):
        """デフォルトツールが登録されていることを確認"""
        all_tools = executor.tool_registry.get_all_tools()
        
        assert len(all_tools) > 0
        assert executor.tool_registry.get_tool('web_search') is not None
        assert executor.tool_registry.get_tool('file_create') is not None
    
    def test_execute_safe_tool(self, executor):
        """安全なツール実行をテスト"""
        result = executor.execute_tool(
            tool_name='web_search',
            args=['test query'],
        )
        
        assert result.execution_id is not None
        assert result.status in ['SUCCESS', 'FAILED']
        assert isinstance(result.safety_score, float)
    
    def test_permission_check_phase(self, executor):
        """権限チェックフェーズをテスト"""
        result = executor.execute_tool(
            tool_name='file_create',
            args=['/tmp/test.txt', 'test'],
            autonomy_level='SEMI_AUTONOMOUS',
        )
        
        assert ExecutionPhase.PERMISSION_CHECK in result.phase_results
    
    def test_execution_phases_complete(self, executor):
        """全実行フェーズが完了することを確認"""
        result = executor.execute_tool(
            tool_name='web_search',
            args=['test'],
        )
        
        # 最低限必要なフェーズが完了していることを確認
        assert ExecutionPhase.PERMISSION_CHECK in result.phase_results
        assert ExecutionPhase.PRODUCTION_EXECUTION in result.phase_results
    
    def test_tool_executor_statistics(self, executor):
        """ツール実行統計をテスト"""
        executor.execute_tool(tool_name='web_search', args=['test1'])
        executor.execute_tool(tool_name='web_search', args=['test2'])
        
        stats = executor.get_tool_executor_statistics()
        
        assert stats['total_executions'] == 2
        assert 'success_rate' in stats
        assert 'avg_safety_score' in stats


class TestEventLoopIntegration:
    """EventLoop 統合テスト"""
    
    @pytest.fixture
    def event_loop(self):
        loop = EventLoop(max_concurrent_tasks=2)
        # ツール実行器を設定（オプション）
        executor = ToolExecutor()
        loop.set_tool_executor(executor)
        return loop
    
    def test_schedule_single_task(self, event_loop):
        """単一タスクをスケジュール"""
        task_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['query'],
        )
        
        assert task_id is not None
        assert event_loop.get_task_status(task_id) == TaskStatus.PENDING
    
    def test_schedule_multiple_tasks(self, event_loop):
        """複数タスクをスケジュール"""
        task_ids = []
        for i in range(3):
            task_id = event_loop.schedule_task(
                tool_name='web_search',
                args=[f'query_{i}'],
                priority=TaskPriority.NORMAL,
            )
            task_ids.append(task_id)
        
        assert len(task_ids) == 3
        pending = event_loop.get_pending_tasks()
        assert len(pending) >= 2  # 少なくとも2つが待機状態
    
    def test_task_cancellation(self, event_loop):
        """タスクキャンセレーションをテスト"""
        task_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['query'],
        )
        
        # キャンセル実行
        cancelled = event_loop.cancel_task(task_id)
        assert cancelled is True
        assert event_loop.get_task_status(task_id) == TaskStatus.CANCELLED
    
    def test_task_dependency_graph(self, event_loop):
        """タスク依存グラフをテスト"""
        task1_id = event_loop.schedule_task(
            tool_name='database_query',
            args=['query1'],
            priority=TaskPriority.HIGH,
        )
        
        task2_id = event_loop.schedule_task(
            tool_name='file_create',
            args=['/tmp/result.txt', 'result'],
            priority=TaskPriority.NORMAL,
            depends_on=[task1_id],  # task1 に依存
        )
        
        # 依存関係が設定されたことを確認
        task2 = event_loop.task_graph.tasks[task2_id]
        assert task1_id in task2.dependencies
    
    def test_circular_dependency_detection(self, event_loop):
        """循環依存の検出をテスト"""
        task1_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['q1'],
        )
        
        task2_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['q2'],
            depends_on=[task1_id],
        )
        
        # task1 が task2 に依存するように設定 → 循環依存
        with pytest.raises(ValueError):
            event_loop.schedule_task(
                tool_name='web_search',
                args=['q3'],
                depends_on=[task2_id],  # task1 をスケジュール後に task2 に依存
            )
            # この時点で task1 を task2 の依存関係に追加したら循環になる
            event_loop.task_graph.add_dependency(task1_id, task2_id)
    
    def test_event_bus_subscription(self, event_loop):
        """イベントバスのサブスクリプションをテスト"""
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        event_loop.event_bus.subscribe(EventType.TASK_CREATED, event_handler)
        
        event_loop.schedule_task(
            tool_name='web_search',
            args=['query'],
        )
        
        assert len(events_received) > 0
        assert events_received[0].event_type == EventType.TASK_CREATED
    
    def test_loop_statistics(self, event_loop):
        """ループ統計をテスト"""
        event_loop.schedule_task(tool_name='web_search', args=['q1'])
        event_loop.schedule_task(tool_name='web_search', args=['q2'])
        
        stats = event_loop.get_loop_statistics()
        
        assert stats['total_tasks'] == 2
        assert stats['max_concurrent'] == 2
        assert 'completed_rate' in stats


class TestFallbackChainIntegration:
    """FallbackChain 統合テスト"""
    
    @pytest.fixture
    def fallback_chain(self):
        return FallbackChain()
    
    def test_get_fallback_options(self, fallback_chain):
        """フォールバックオプションを取得"""
        options = fallback_chain.get_fallback_options(
            tool_name='web_search',
            args=['query'],
            error='Connection timeout',
        )
        
        assert len(options) > 0
        # 最初のオプションは最高信頼度
        assert options[0].confidence >= options[-1].confidence
    
    def test_fallback_strategy_priority(self, fallback_chain):
        """フォールバック戦略の優先度確認"""
        options = fallback_chain.get_fallback_options(
            tool_name='file_create',
            args=['/tmp/test.txt', 'content'],
            error='Permission denied',
        )
        
        # Error Learning の提案があればそれが最初
        # なければ、標準戦略が優先度順にソートされている
        strategies = [opt.strategy for opt in options]
        assert len(strategies) > 0
    
    def test_fallback_chain_execution_with_retry(self, fallback_chain):
        """フォールバックチェーンの実行（リトライ）をテスト"""
        tool_executor = ToolExecutor()
        
        success, result, attempts = fallback_chain.execute_fallback_chain(
            tool_name='web_search',
            args=['query'],
            error='Timeout',
            tool_executor=tool_executor,
        )
        
        # リトライが実行されたことを確認
        assert len(attempts) > 0
        assert attempts[0].attempt_number == 1
    
    def test_suggested_modified_args(self, fallback_chain):
        """修正されたパラメータ提案をテスト"""
        modified = fallback_chain._suggest_modified_args(
            tool_name='web_search',
            args=['very long query string that might cause timeout'],
            error='Operation timed out',
        )
        
        # タイムアウト時はパラメータが簡略化される
        assert len(str(modified[0])) <= len('very long query string that might cause timeout')
    
    def test_degrade_quality_fallback(self, fallback_chain):
        """品質低下フォールバックをテスト"""
        original_args = ['arg1', 'arg2', 'arg3']
        degraded = fallback_chain._degrade_args(original_args)
        
        # 簡易版は最初のパラメータのみ
        assert len(degraded) == 1
        assert degraded[0] == 'arg1'
    
    def test_fallback_statistics(self, fallback_chain):
        """フォールバック統計をテスト"""
        tool_executor = ToolExecutor()
        
        # 複数のフォールバック試行を実行
        for i in range(2):
            fallback_chain.execute_fallback_chain(
                tool_name='web_search',
                args=[f'query_{i}'],
                error='Test error',
                tool_executor=tool_executor,
            )
        
        stats = fallback_chain.get_fallback_statistics()
        
        assert stats['total_attempts'] > 0
        assert 'by_strategy' in stats


class TestPhase4FullIntegration:
    """Phase 4 全体統合テスト"""
    
    @pytest.fixture
    def components(self):
        """全ての Phase 4 コンポーネントを初期化"""
        return {
            'executor': ToolExecutor(),
            'event_loop': EventLoop(max_concurrent_tasks=2),
            'fallback_chain': FallbackChain(),
        }
    
    def test_tool_execution_complete_workflow(self, components):
        """ツール実行の完全なワークフロー"""
        executor = components['executor']
        
        # ツール実行
        result = executor.execute_tool(
            tool_name='web_search',
            args=['test query'],
        )
        
        # 実行結果の検証
        assert result.execution_id is not None
        assert result.tool_name == 'web_search'
        assert 0.0 <= result.safety_score <= 1.0
    
    def test_event_loop_task_execution(self, components):
        """イベントループのタスク実行"""
        event_loop = components['event_loop']
        executor = components['executor']
        event_loop.set_tool_executor(executor)
        
        # タスクをスケジュール
        task_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['query'],
            priority=TaskPriority.NORMAL,
        )
        
        # ループを起動
        event_loop.start()
        
        # loop が動作していることを確認
        assert event_loop.is_running
        
        # クリーンアップ
        event_loop.stop()
    
    def test_fallback_integration_with_executor(self, components):
        """フォールバックチェーンの Executor 統合"""
        executor = components['executor']
        fallback = components['fallback_chain']
        
        # フォールバック実行
        success, result, attempts = fallback.execute_fallback_chain(
            tool_name='web_search',
            args=['query'],
            error='Temporary failure',
            tool_executor=executor,
        )
        
        # 少なくとも1つの試行があることを確認
        assert len(attempts) > 0
    
    def test_permission_explainability_integration(self, components):
        """権限・説明責任の Phase 3 との連携"""
        executor = components['executor']
        
        # Phase 3 モジュールを設定（オプション）
        # executor.permission_manager = PermissionManager()
        # executor.decision_explainer = DecisionExplainer()
        
        result = executor.execute_tool(
            tool_name='file_create',
            args=['/tmp/test.txt', 'content'],
        )
        
        # 権限チェックが実行されたことを確認
        assert ExecutionPhase.PERMISSION_CHECK in result.phase_results
    
    def test_full_pipeline_sequence(self, components):
        """フルパイプライン実行シーケンス"""
        executor = components['executor']
        event_loop = components['event_loop']
        fallback = components['fallback_chain']
        
        # 1. 直接実行
        result1 = executor.execute_tool(
            tool_name='web_search',
            args=['query1'],
        )
        assert result1 is not None
        
        # 2. イベントループでタスク管理
        task_id = event_loop.schedule_task(
            tool_name='web_search',
            args=['query2'],
        )
        assert task_id is not None
        
        # 3. 失敗時のフォールバック
        options = fallback.get_fallback_options(
            tool_name='web_search',
            args=['query3'],
            error='Network error',
        )
        assert len(options) > 0


# テスト実行
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
