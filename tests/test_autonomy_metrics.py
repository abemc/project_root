"""
エージェント自律性指標テストスイート

Task 5: エージェント自律性指標の実装テスト
"""

import pytest
from datetime import datetime
from src.agent.autonomy.autonomy_scorer import (
    AutonomyScorer,
    DimensionalAutonomy,
    evaluate_autonomy_simple,
)
from src.agent.autonomy.decision_analyzer import (
    DecisionAnalyzer,
    DecisionType,
    DecisionQuality,
)
from src.agent.autonomy.planning_measurer import (
    PlanningCapacityMeasurer,
    PlanQuality,
)
from src.agent.autonomy.task_tracker import (
    TaskSuccessTracker,
    TaskStatus,
    TaskType,
    ErrorCategory,
)


class TestAutonomyScorer:
    """自律性スコアラーのテスト"""
    
    def test_scorer_initialization(self):
        """スコアラー初期化テスト"""
        scorer = AutonomyScorer()
        assert scorer.evaluation_history == []
        assert len(scorer.LEVEL_DEFINITIONS) == 5
    
    def test_calculate_score_high_autonomy(self):
        """高自律性スコア計算テスト"""
        scorer = AutonomyScorer()
        score = scorer.calculate_score(
            task_success_rate=0.95,
            user_intervention_rate=0.0,
            error_recovery_rate=0.90,
            strategy_switches=2,
            learning_rate=0.8,
            total_attempts=10,
        )
        
        assert score.overall_score >= 80  # Autonomous以上
        assert score.autonomy_level == "Autonomous"
        assert len(score.strengths) > 0
    
    def test_calculate_score_low_autonomy(self):
        """低自律性スコア計算テスト"""
        scorer = AutonomyScorer()
        score = scorer.calculate_score(
            task_success_rate=0.3,
            user_intervention_rate=0.8,
            error_recovery_rate=0.2,
            strategy_switches=0,
            learning_rate=0.1,
            total_attempts=3,
        )
        
        assert score.overall_score < 40
        assert score.autonomy_level in ["Dependent", "Assisted"]
        assert len(score.weaknesses) > 0
    
    def test_dimensional_autonomy_average(self):
        """多次元自律性平均テスト"""
        dimensions = DimensionalAutonomy(
            goal_achievement=0.8,
            decision_independence=0.9,
            error_recovery=0.7,
            strategy_adaptation=0.85,
            learning_capability=0.75,
        )
        
        average = dimensions.get_average()
        assert 0.70 < average < 0.90
    
    def test_normalize_function(self):
        """正規化関数テスト"""
        scorer = AutonomyScorer()
        
        assert scorer._normalize(0.5, 0, 1) == 0.5
        assert scorer._normalize(0, 0, 1) == 0.0
        assert scorer._normalize(1, 0, 1) == 1.0
        assert scorer._normalize(2, 0, 1) == 1.0  # 上限チェック
        assert scorer._normalize(-1, 0, 1) == 0.0  # 下限チェック
    
    def test_improvement_trend(self):
        """改善傾向計算テスト"""
        scorer = AutonomyScorer()
        
        # 最初のスコア
        scorer.calculate_score(0.5, 0.5, 0.5, 1, 0.3, 5)
        # 改善したスコア
        scorer.calculate_score(0.9, 0.1, 0.85, 2, 0.7, 10)
        
        trend = scorer.get_improvement_trend()
        assert trend is not None
        assert trend > 0  # 正の成長
    
    def test_simple_autonomy_evaluation(self):
        """簡易版自律性評価テスト"""
        score = evaluate_autonomy_simple(0.95, 0.0)
        assert score >= 80
        
        score = evaluate_autonomy_simple(0.5, 0.5)
        assert 30 <= score <= 70


class TestDecisionAnalyzer:
    """意思決定分析エンジンのテスト"""
    
    def test_create_flow(self):
        """フロー作成テスト"""
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_001", "サンプルタスク")
        
        assert flow.task_id == "task_001"
        assert flow.start_time is not None
        assert len(flow.steps) == 0
    
    def test_record_decision(self):
        """意思決定記録テスト"""
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_001", "テスト")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="ユーザー入力が明確",
            options=["オプションA", "オプションB"],
            selected="オプションA",
            reasoning="最も効率的",
            confidence=0.9,
        )
        
        assert step.step_id == 1
        assert step.decision_type == DecisionType.AUTONOMOUS
        assert len(flow.steps) == 1
    
    def test_autonomy_score_calculation(self):
        """フロー自律性スコア計算テスト"""
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_001", "テスト")
        
        # 自律的な決定を3つ追加
        for i in range(3):
            analyzer.record_decision(
                flow=flow,
                decision_type=DecisionType.AUTONOMOUS,
                context=f"コンテキスト{i}",
                options=["A", "B"],
                selected="A",
                reasoning="理由",
                confidence=0.8,
            )
        
        autonomy_score = flow.get_autonomy_score()
        assert autonomy_score == 1.0  # 全て自律的
    
    def test_quality_evaluation(self):
        """品質評価テスト"""
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_001", "テスト")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="テスト",
            options=["A"],
            selected="A",
            reasoning="テスト",
            confidence=0.8,
        )
        
        # 成功した決定として評価
        quality = analyzer.evaluate_step_quality(step, True)
        assert quality == DecisionQuality.OPTIMAL
        
        # 失敗した決定として評価
        quality = analyzer.evaluate_step_quality(step, False)
        assert quality == DecisionQuality.SUBOPTIMAL
    
    def test_complete_flow(self):
        """フロー完了テスト"""
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_001", "テスト")
        
        analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="テスト",
            options=["A"],
            selected="A",
            reasoning="テスト",
            confidence=0.8,
        )
        
        completed_flow = analyzer.complete_flow(flow, True)
        assert completed_flow.overall_success is True
        assert completed_flow.end_time is not None
        assert len(analyzer.flows) == 1
    
    def test_decision_pattern_analysis(self):
        """意思決定パターン分析テスト"""
        analyzer = DecisionAnalyzer()
        
        # 複数のフローを作成
        for task_id in range(3):
            flow = analyzer.create_flow(f"task_{task_id}", "テスト")
            analyzer.record_decision(
                flow=flow,
                decision_type=DecisionType.AUTONOMOUS,
                context="テスト",
                options=["A"],
                selected="A",
                reasoning="テスト",
                confidence=0.8,
            )
            analyzer.complete_flow(flow, True)
        
        patterns = analyzer.analyze_decision_patterns()
        assert patterns["total_flows"] == 3
        assert patterns["success_rate"] == 1.0
        assert patterns["average_autonomy"] == 1.0


class TestPlanningMeasurer:
    """計画能力測定のテスト"""
    
    def test_create_plan(self):
        """計画作成テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan(
            "plan_001",
            "テストタスク",
        )
        
        assert plan.plan_id == "plan_001"
        assert plan.total_estimated_time == 0.0
    
    def test_add_plan_steps(self):
        """計画ステップ追加テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_001", "テスト")
        
        for i in range(5):
            measurer.add_plan_step(plan, f"ステップ{i}", 10.0)
        
        assert len(plan.steps) == 5
        assert plan.total_estimated_time == 50.0
    
    def test_execute_step(self):
        """ステップ実行テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_001", "テスト")
        
        step = measurer.add_plan_step(plan, "ステップ1", 10.0)
        measurer.execute_step(step, 10.5, True)
        
        assert step.status == "completed"
        assert step.success is True
        assert step.actual_duration == 10.5
    
    def test_complete_plan_optimal(self):
        """最適計画完了テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_001", "テスト", constraints=[], uncertain_factors=[])
        
        # 最適なステップ数（5-15）
        for i in range(8):
            step = measurer.add_plan_step(plan, f"ステップ{i}", 10.0)
            measurer.execute_step(step, 10.0, True)
        
        measurer.complete_plan(plan, True)
        
        assert plan.plan_quality == PlanQuality.OPTIMAL
        assert plan.success is True
    
    def test_complete_plan_inefficient(self):
        """非効率計画完了テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_001", "テスト", constraints=[], uncertain_factors=[])
        
        # 過度に多いステップ数
        for i in range(25):
            step = measurer.add_plan_step(plan, f"ステップ{i}", 10.0)
            measurer.execute_step(step, 15.0, i < 20)  # 最後の5つは失敗
        
        measurer.complete_plan(plan, True)
        
        assert plan.plan_quality in [PlanQuality.INEFFICIENT, PlanQuality.ACCEPTABLE]
    
    def test_replan_tracking(self):
        """リプラン追跡テスト"""
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_001", "テスト", constraints=[], uncertain_factors=[])
        
        step = measurer.add_plan_step(plan, "ステップ1", 10.0)
        measurer.mark_replan_needed(plan, step)
        measurer.mark_replan_needed(plan, step)
        
        assert plan.replan_count == 2
        assert step.replan_required is True


class TestTaskSuccessTracker:
    """タスク成功追跡のテスト"""
    
    def test_create_task(self):
        """タスク作成テスト"""
        tracker = TaskSuccessTracker()
        task = tracker.create_task(
            "task_001",
            "テストタスク",
            TaskType.SIMPLE,
        )
        
        assert task.task_id == "task_001"
        assert task.task_type == TaskType.SIMPLE
    
    def test_record_attempt_success(self):
        """成功試行記録テスト"""
        tracker = TaskSuccessTracker()
        task = tracker.create_task("task_001", "テスト", TaskType.SIMPLE)
        
        attempt = tracker.record_attempt(
            task,
            TaskStatus.COMPLETED,
            datetime.now().isoformat(),
            duration=5.0,
            steps_taken=3,
        )
        
        assert attempt.is_successful() is True
        assert task.get_attempt_count() == 1
    
    def test_complete_task(self):
        """タスク完了テスト"""
        tracker = TaskSuccessTracker()
        task = tracker.create_task("task_001", "テスト", TaskType.SIMPLE)
        
        tracker.record_attempt(
            task,
            TaskStatus.COMPLETED,
            datetime.now().isoformat(),
            duration=5.0,
        )
        
        tracker.complete_task(task, TaskStatus.COMPLETED, "成功")
        
        assert task.is_successful() is True
        assert len(tracker.tasks) == 1
    
    def test_overall_success_rate(self):
        """全体成功率テスト"""
        tracker = TaskSuccessTracker()
        
        # 3つのタスク：2つ成功、1つ失敗
        for i in range(2):
            task = tracker.create_task(f"task_{i}", "テスト", TaskType.SIMPLE)
            tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
            tracker.complete_task(task, TaskStatus.COMPLETED)
        
        task = tracker.create_task("task_2", "テスト", TaskType.SIMPLE)
        tracker.record_attempt(task, TaskStatus.FAILED, datetime.now().isoformat(), error="エラー")
        tracker.complete_task(task, TaskStatus.FAILED)
        
        assert tracker.get_overall_success_rate() == pytest.approx(2/3, 0.01)
    
    def test_success_rate_by_type(self):
        """タイプ別成功率テスト"""
        tracker = TaskSuccessTracker()
        
        # Simple タスク：2つ成功
        for i in range(2):
            task = tracker.create_task(f"simple_{i}", "テスト", TaskType.SIMPLE)
            tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
            tracker.complete_task(task, TaskStatus.COMPLETED)
        
        # Complex タスク：1つ成功、1つ失敗
        task = tracker.create_task("complex_0", "テスト", TaskType.COMPLEX)
        tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
        tracker.complete_task(task, TaskStatus.COMPLETED)
        
        task = tracker.create_task("complex_1", "テスト", TaskType.COMPLEX)
        tracker.record_attempt(task, TaskStatus.FAILED, datetime.now().isoformat(), error="エラー")
        tracker.complete_task(task, TaskStatus.FAILED)
        
        rates = tracker.get_success_rate_by_type()
        assert rates["simple"] == 1.0
        assert rates["complex"] == 0.5
    
    def test_multi_step_completion_rate(self):
        """複数段階完成率テスト"""
        tracker = TaskSuccessTracker()
        
        # Multi-step: 2つ成功
        for i in range(2):
            task = tracker.create_task(f"multi_{i}", "テスト", TaskType.MULTI_STEP)
            tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
            tracker.complete_task(task, TaskStatus.COMPLETED)
        
        # Complex: 1つ失敗
        task = tracker.create_task("complex_0", "テスト", TaskType.COMPLEX)
        tracker.record_attempt(task, TaskStatus.FAILED, datetime.now().isoformat(), error="エラー")
        tracker.complete_task(task, TaskStatus.FAILED)
        
        rate = tracker.get_multi_step_completion_rate()
        assert rate == pytest.approx(2/3, 0.01)
    
    def test_error_pattern_analysis(self):
        """エラーパターン分析テスト"""
        tracker = TaskSuccessTracker()
        
        task = tracker.create_task("task_001", "テスト", TaskType.SIMPLE)
        tracker.record_attempt(
            task,
            TaskStatus.FAILED,
            datetime.now().isoformat(),
            error="タイムアウト",
            error_category=ErrorCategory.TIMEOUT_ERROR,
        )
        tracker.complete_task(task, TaskStatus.FAILED)
        
        patterns = tracker.get_error_pattern_analysis()
        assert "timeout_error" in patterns
        assert patterns["timeout_error"]["count"] == 1
    
    def test_retry_statistics(self):
        """リトライ統計テスト"""
        tracker = TaskSuccessTracker()
        
        # 3試行で成功
        task = tracker.create_task("task_001", "テスト", TaskType.SIMPLE)
        tracker.record_attempt(task, TaskStatus.FAILED, datetime.now().isoformat(), error="エラー1")
        tracker.record_attempt(task, TaskStatus.FAILED, datetime.now().isoformat(), error="エラー2")
        tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
        tracker.complete_task(task, TaskStatus.COMPLETED)
        
        stats = tracker.get_retry_statistics()
        assert stats["average_attempts"] == 3.0
        assert stats["first_attempt_success_rate"] == 0.0
    
    def test_autonomy_readiness_score(self):
        """自律性準備度スコアテスト"""
        tracker = TaskSuccessTracker()
        
        # 複数の成功タスク
        for i in range(5):
            task = tracker.create_task(f"task_{i}", "テスト", TaskType.MULTI_STEP)
            tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat())
            tracker.complete_task(task, TaskStatus.COMPLETED)
        
        score = tracker.get_autonomy_readiness_score()
        assert 0.8 <= score <= 1.0  # 高い自律性準備度


class TestIntegration:
    """統合テスト"""
    
    def test_autonomy_workflow(self):
        """完全な自律性評価ワークフロー"""
        # 自律性スコアラー
        scorer = AutonomyScorer()
        score1 = scorer.calculate_score(
            task_success_rate=0.8,
            user_intervention_rate=0.1,
            error_recovery_rate=0.75,
            strategy_switches=2,
            learning_rate=0.6,
            total_attempts=8,
        )
        
        # 意思決定分析
        analyzer = DecisionAnalyzer()
        flow = analyzer.create_flow("task_complex", "複雑なタスク")
        
        for i in range(5):
            analyzer.record_decision(
                flow=flow,
                decision_type=DecisionType.AUTONOMOUS if i % 2 == 0 else DecisionType.GUIDED,
                context=f"ステップ{i}",
                options=["A", "B"],
                selected="A",
                reasoning="最適化",
                confidence=0.8,
            )
        
        analyzer.complete_flow(flow, True)
        
        # 計画能力測定
        measurer = PlanningCapacityMeasurer()
        plan = measurer.create_plan("plan_complex", "複雑な計画")
        
        for i in range(8):
            step = measurer.add_plan_step(plan, f"ステップ{i}", 10.0)
            measurer.execute_step(step, 10.0, True)
        
        measurer.complete_plan(plan, True)
        
        # タスク追跡
        tracker = TaskSuccessTracker()
        task = tracker.create_task("task_main", "メインタスク", TaskType.COMPLEX)
        tracker.record_attempt(task, TaskStatus.COMPLETED, datetime.now().isoformat(), duration=80.0)
        tracker.complete_task(task, TaskStatus.COMPLETED)
        
        # 検証
        assert score1.overall_score >= 60
        assert flow.get_autonomy_score() >= 0.4
        assert plan.plan_quality == PlanQuality.OPTIMAL
        assert tracker.get_overall_success_rate() == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
