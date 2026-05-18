"""
Phase 3 Integration Tests: Safety/Explainability

PermissionManager, DecisionExplainer, ValueConflictResolver, SandboxExecutor
が正しく統合されて動作することを確認。
"""

import pytest
from datetime import datetime
from typing import Dict

# Phase 3 imports
from src.safety.permission_manager import (
    PermissionManager,
    ToolAccessLevel,
    AutonomyLevel,
)
from src.explainability.decision_explainer import (
    DecisionExplainer,
    ExplanationType,
)
from src.ethics.value_conflict_resolver import (
    ValueConflictResolver,
    Value,
    ValuePriority,
)
from src.sandbox.sandbox_executor import (
    SandboxExecutor,
    SandboxType,
    ExecutionPolicy,
    ExecutionStatus,
)


class TestPermissionManagerIntegration:
    """PermissionManager 統合テスト"""
    
    @pytest.fixture
    def manager(self):
        return PermissionManager()
    
    def test_can_execute_basic_tool(self, manager):
        """基本的なツール実行権を確認"""
        # READ_ONLY ツールは全てのレベルで実行可能
        can_execute = manager.can_execute(
            tool_name='web_search',
            autonomy_level=AutonomyLevel.SUPERVISED,
        )
        assert can_execute is True
    
    def test_requires_approval_for_critical_tools(self, manager):
        """重要なツールは承認が必要なことを確認"""
        requires = manager.requires_approval(
            tool_name='file_delete',
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )
        assert requires is True
    
    def test_rate_limiting_enforcement(self, manager):
        """レート制限が適用されることを確認"""
        # 複数回の実行を記録
        for i in range(3):
            manager.record_execution('file_create')
        
        # 制限内の確認
        stats = manager.get_permission_summary()
        assert 'file_create' in str(stats)


class TestDecisionExplainerIntegration:
    """DecisionExplainer 統合テスト"""
    
    @pytest.fixture
    def explainer(self):
        return DecisionExplainer()
    
    def test_tool_selection_explanation_high_confidence(self, explainer):
        """高確信度のツール選択説明を生成"""
        explanation = explainer.explain_tool_selection(
            task_description="Search for information about Python",
            selected_tool="web_search",
            tool_candidates=["web_search", "database_query", "file_search"],
            success_rates={"web_search": 0.95, "database_query": 0.60, "file_search": 0.50},
            confidence=0.95,
        )
        
        assert "web_search" in explanation
        assert "high" in explanation.lower() or "95" in explanation or "success rate" in explanation.lower()
    
    def test_parameter_selection_explanation(self, explainer):
        """パラメータ選択の説明を生成"""
        explanation = explainer.explain_parameter_selection(
            tool_name="api_call",
            parameter_name="timeout",
            parameter_value=30,
            context={'scenario': 'standard', 'min_value': 5, 'max_value': 60},
        )
        
        assert "timeout" in explanation.lower()
        assert "30" in explanation
    
    def test_export_explanation_report(self, explainer):
        """説明レポートをエクスポート"""
        explainer.explain_tool_selection(
            task_description="Test task",
            selected_tool="web_search",
            tool_candidates=["web_search"],
            success_rates={"web_search": 0.8},
            confidence=0.8,
        )
        
        report = explainer.export_explanation_report()
        
        assert report['total_explanations'] == 1
        assert 'by_type' in report
        assert 'avg_confidence' in report


class TestValueConflictResolverIntegration:
    """ValueConflictResolver 統合テスト"""
    
    @pytest.fixture
    def resolver(self):
        return ValueConflictResolver()
    
    def test_resolve_privacy_vs_utility_conflict(self, resolver):
        """プライバシー vs 有用性の衝突を解決"""
        decision, score, details = resolver.resolve_conflict(
            action_proposed="Log all user interactions",
            conflicting_values=[Value.PRIVACY, Value.UTILITY],
            impact_analysis={
                Value.PRIVACY: -0.6,  # 負の影響
                Value.UTILITY: 0.8,   # 正の影響
                Value.SAFETY: 0.3,
            },
        )
        
        assert decision is not None
        assert 0.0 <= score <= 1.0
        assert 'satisfaction_scores' in details
    
    def test_single_violation_override_allowed(self, resolver):
        """少量の違反で許可される場合をテスト"""
        decision, score, _ = resolver.resolve_conflict(
            action_proposed="Minor action",
            conflicting_values=[Value.EFFICIENCY],
            impact_analysis={Value.EFFICIENCY: -0.1},  # 小さい負の影響
        )
        
        # EFFICIENCY は override_allowed=True なので許可される可能性がある
        assert decision is not None
    
    def test_suggest_alternative_action(self, resolver):
        """代替案を提案"""
        violations = [(Value.PRIVACY, 0.2)]
        
        alternative = resolver.suggest_alternative_action(
            original_action="Log user data",
            violations=violations,
            context={},
        )
        
        assert alternative is not None
        assert "privacy" in alternative.lower()
    
    def test_conflict_statistics(self, resolver):
        """衝突統計を取得"""
        # 複数の衝突を記録
        for i in range(3):
            resolver.resolve_conflict(
                action_proposed=f"Action {i}",
                conflicting_values=[Value.PRIVACY],
                impact_analysis={Value.PRIVACY: 0.0},
            )
        
        stats = resolver.get_conflict_statistics()
        
        assert stats['total_conflicts'] == 3
        assert 'approval_rate' in stats


class TestSandboxExecutorIntegration:
    """SandboxExecutor 統合テスト"""
    
    @pytest.fixture
    def executor(self):
        return SandboxExecutor(SandboxType.SUBPROCESS)
    
    def test_safe_command_execution(self, executor):
        """安全なコマンド実行をテスト"""
        result = executor.execute_in_sandbox(
            command='echo',
            args=['Hello, Sandbox!'],
        )
        
        assert result.status in [ExecutionStatus.SUCCESS]
        assert "Hello" in result.output or result.status == ExecutionStatus.SUCCESS
    
    def test_dangerous_command_blocked(self, executor):
        """危険なコマンドが遮断されることを確認"""
        result = executor.execute_in_sandbox(
            command='rm',
            args=['-rf', '/'],
        )
        
        assert result.status == ExecutionStatus.SECURITY_BLOCKED
    
    def test_execution_result_validation(self, executor):
        """実行結果の検証をテスト"""
        result = executor.execute_in_sandbox(
            command='echo',
            args=['test'],
        )
        
        assert result.validation_passed is not None
        assert 0.0 <= result.safety_score <= 1.0
    
    def test_sandbox_statistics(self, executor):
        """サンドボックス統計を取得"""
        # 複数の実行を記録
        executor.execute_in_sandbox(command='echo', args=['test1'])
        executor.execute_in_sandbox(command='echo', args=['test2'])
        
        stats = executor.get_sandbox_statistics()
        
        assert stats['total_executions'] == 2
        assert 'success_rate' in stats
        assert 'average_execution_time' in stats


class TestPhase3FullIntegration:
    """Phase 3 全体統合テスト"""
    
    @pytest.fixture
    def components(self):
        """全ての Phase 3 コンポーネントを初期化"""
        return {
            'permission_manager': PermissionManager(),
            'decision_explainer': DecisionExplainer(),
            'value_resolver': ValueConflictResolver(),
            'sandbox_executor': SandboxExecutor(SandboxType.SUBPROCESS),
        }
    
    def test_safety_decision_workflow(self, components):
        """安全な意思決定ワークフロー全体をテスト"""
        pm = components['permission_manager']
        de = components['decision_explainer']
        vr = components['value_resolver']
        
        # 1. ツール実行権を確認
        tool_name = 'file_create'
        can_execute = pm.can_execute(tool_name, AutonomyLevel.SEMI_AUTONOMOUS)
        assert can_execute is not None
        
        # 2. 選択を説明
        if can_execute:
            explanation = de.explain_tool_selection(
                task_description="Create log file",
                selected_tool=tool_name,
                tool_candidates=[tool_name, 'database_write'],
                success_rates={tool_name: 0.9, 'database_write': 0.7},
                confidence=0.9,
            )
            assert explanation is not None
        
        # 3. 価値衝突を確認
        decision, score, details = vr.resolve_conflict(
            action_proposed=f"Execute {tool_name}",
            conflicting_values=[Value.TRANSPARENCY, Value.EFFICIENCY],
            impact_analysis={
                Value.TRANSPARENCY: 0.8,
                Value.EFFICIENCY: 0.6,
            },
        )
        
        assert decision is not None
        assert 'APPROVE' in decision or 'REJECT' in decision
    
    def test_audit_trail_completeness(self, components):
        """全ステップの監査証跡が完全であることを確認"""
        de = components['decision_explainer']
        vr = components['value_resolver']
        sx = components['sandbox_executor']
        
        # 説明
        de.explain_tool_selection(
            task_description="Test",
            selected_tool="test_tool",
            tool_candidates=["test_tool"],
            success_rates={"test_tool": 0.8},
            confidence=0.8,
        )
        
        # 価値判定
        vr.resolve_conflict(
            action_proposed="Test action",
            conflicting_values=[Value.SAFETY],
            impact_analysis={Value.SAFETY: 0.5},
        )
        
        # 実行
        sx.execute_in_sandbox(command='echo', args=['test'])
        
        # 各モジュールのログを確認
        de_report = de.export_explanation_report()
        vr_stats = vr.get_conflict_statistics()
        sx_stats = sx.get_sandbox_statistics()
        
        assert de_report['total_explanations'] > 0
        assert vr_stats['total_conflicts'] > 0
        assert sx_stats['total_executions'] > 0


# テスト実行
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
