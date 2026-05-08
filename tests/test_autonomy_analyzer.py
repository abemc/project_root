"""
エージェント自律性分析テスト

DecisionAnalyzer の機能を包括的にテストします。
"""

import pytest
from pathlib import Path
from datetime import datetime
from src.agent.autonomy.decision_analyzer import (
    DecisionAnalyzer,
    DecisionFlow,
    DecisionStep,
    DecisionType,
    DecisionQuality,
)


class TestDecisionStep:
    """DecisionStep のテスト"""
    
    def test_create_decision_step(self):
        """ステップ作成テスト"""
        step = DecisionStep(
            step_id=1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test context",
            options_considered=["A", "B", "C"],
            selected_option="B",
            reasoning="Best option",
            confidence=0.95,
        )
        
        assert step.step_id == 1
        assert step.decision_type == DecisionType.AUTONOMOUS
        assert step.selected_option == "B"
        assert step.confidence == 0.95
    
    def test_step_to_dict(self):
        """ステップの辞書変換テスト"""
        step = DecisionStep(
            step_id=1,
            decision_type=DecisionType.GUIDED,
            context="Test",
            options_considered=["A"],
            selected_option="A",
            confidence=0.8,
            quality=DecisionQuality.GOOD,
        )
        
        result = step.get_dict()
        assert result["step_id"] == 1
        assert result["decision_type"] == "guided"
        assert result["quality"] == "good"


class TestDecisionFlow:
    """DecisionFlow のテスト"""
    
    def test_create_flow(self):
        """フロー作成テスト"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test task",
        )
        
        assert flow.task_id == "task_001"
        assert len(flow.steps) == 0
    
    def test_add_step_to_flow(self):
        """ステップ追加テスト"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test task",
        )
        
        step = DecisionStep(
            step_id=1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options_considered=["A"],
            selected_option="A",
            confidence=0.9,
        )
        
        flow.add_step(step)
        assert len(flow.steps) == 1
        assert flow.steps[0].timestamp is not None
    
    def test_autonomy_score_all_autonomous(self):
        """自律性スコア - 全て自律の場合"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test",
        )
        
        for i in range(3):
            step = DecisionStep(
                step_id=i+1,
                decision_type=DecisionType.AUTONOMOUS,
                context="Test",
                options_considered=["A"],
                selected_option="A",
                confidence=0.9,
            )
            flow.add_step(step)
        
        assert flow.get_autonomy_score() == 1.0
    
    def test_autonomy_score_mixed(self):
        """自律性スコア - 混合の場合"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test",
        )
        
        # 自律決定
        step1 = DecisionStep(
            step_id=1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options_considered=["A"],
            selected_option="A",
            confidence=0.9,
        )
        flow.add_step(step1)
        
        # ガイド付き決定
        step2 = DecisionStep(
            step_id=2,
            decision_type=DecisionType.GUIDED,
            context="Test",
            options_considered=["B"],
            selected_option="B",
            confidence=0.8,
        )
        flow.add_step(step2)
        
        assert flow.get_autonomy_score() == 0.5
    
    def test_decision_quality_score(self):
        """品質スコア計算テスト"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test",
        )
        
        step1 = DecisionStep(
            step_id=1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options_considered=["A"],
            selected_option="A",
            confidence=0.9,
            quality=DecisionQuality.OPTIMAL,
        )
        flow.add_step(step1)
        
        step2 = DecisionStep(
            step_id=2,
            decision_type=DecisionType.GUIDED,
            context="Test",
            options_considered=["B"],
            selected_option="B",
            confidence=0.8,
            quality=DecisionQuality.GOOD,
        )
        flow.add_step(step2)
        
        # (1.0 + 0.85) / 2 = 0.925
        assert abs(flow.get_decision_quality_score() - 0.925) < 0.01
    
    def test_intervention_rate(self):
        """ユーザー介入率テスト"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test",
        )
        
        step1 = DecisionStep(
            step_id=1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options_considered=["A"],
            selected_option="A",
            confidence=0.9,
            user_intervention=False,
        )
        flow.add_step(step1)
        
        step2 = DecisionStep(
            step_id=2,
            decision_type=DecisionType.GUIDED,
            context="Test",
            options_considered=["B"],
            selected_option="B",
            confidence=0.8,
            user_intervention=True,
        )
        flow.add_step(step2)
        
        assert flow.get_intervention_rate() == 0.5
    
    def test_average_confidence(self):
        """平均信頼度テスト"""
        flow = DecisionFlow(
            task_id="task_001",
            task_description="Test",
        )
        
        for conf in [0.8, 0.9, 0.7]:
            step = DecisionStep(
                step_id=len(flow.steps)+1,
                decision_type=DecisionType.AUTONOMOUS,
                context="Test",
                options_considered=["A"],
                selected_option="A",
                confidence=conf,
            )
            flow.add_step(step)
        
        expected = (0.8 + 0.9 + 0.7) / 3
        assert abs(flow.get_average_confidence() - expected) < 0.01


class TestDecisionAnalyzer:
    """DecisionAnalyzer のテスト"""
    
    @pytest.fixture
    def analyzer(self):
        """分析器のフィクスチャ"""
        return DecisionAnalyzer()
    
    def test_create_flow(self, analyzer):
        """フロー作成テスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        assert flow.task_id == "task_001"
        assert flow.start_time is not None
    
    def test_record_decision(self, analyzer):
        """決定記録テスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test context",
            options=["A", "B"],
            selected="A",
            reasoning="Best option",
            confidence=0.9,
        )
        
        assert len(flow.steps) == 1
        assert step.selected_option == "A"
    
    def test_evaluate_step_quality_autonomous_success(self, analyzer):
        """品質評価テスト - 自律成功"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        
        quality = analyzer.evaluate_step_quality(step, actual_outcome=True)
        assert quality == DecisionQuality.OPTIMAL
    
    def test_evaluate_step_quality_autonomous_failure(self, analyzer):
        """品質評価テスト - 自律失敗"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.5,  # 低い信頼度
        )
        
        quality = analyzer.evaluate_step_quality(step, actual_outcome=False)
        assert quality == DecisionQuality.SUBOPTIMAL
    
    def test_evaluate_step_quality_overconfidence_failure(self, analyzer):
        """品質評価テスト - 過信による失敗"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.95,
        )
        
        quality = analyzer.evaluate_step_quality(step, actual_outcome=False)
        assert quality == DecisionQuality.FAILED
    
    def test_complete_flow(self, analyzer):
        """フロー完了テスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        
        analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        
        analyzer.complete_flow(flow, overall_success=True)
        
        assert flow.overall_success is True
        assert flow.end_time is not None
        assert flow in analyzer.flows
    
    def test_analyze_decision_patterns(self, analyzer):
        """決定パターン分析テスト"""
        # 成功フロー
        flow1 = analyzer.create_flow("task_001", "Test task 1")
        analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.complete_flow(flow1, overall_success=True)
        
        # 失敗フロー
        flow2 = analyzer.create_flow("task_002", "Test task 2")
        analyzer.record_decision(
            flow=flow2,
            decision_type=DecisionType.FALLBACK,
            context="Test",
            options=["B"],
            selected="B",
            reasoning="Test",
            confidence=0.5,
        )
        analyzer.complete_flow(flow2, overall_success=False)
        
        patterns = analyzer.analyze_decision_patterns()
        
        assert patterns["total_flows"] == 2
        assert patterns["success_rate"] == 0.5
        assert "autonomous" in patterns["decision_type_distribution"]
    
    def test_analyze_failure_patterns(self, analyzer):
        """失敗パターン分析テスト"""
        # 失敗フロー
        flow1 = analyzer.create_flow("task_001", "Test task 1")
        step = analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.95,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=False)
        analyzer.complete_flow(flow1, overall_success=False)
        
        # 成功フロー
        flow2 = analyzer.create_flow("task_002", "Test task 2")
        step2 = analyzer.record_decision(
            flow=flow2,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["B"],
            selected="B",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.evaluate_step_quality(step2, actual_outcome=True)
        analyzer.complete_flow(flow2, overall_success=True)
        
        analysis = analyzer.analyze_failure_patterns()
        
        assert analysis["failure_rate"] == 0.5
        assert analysis["total_failures"] == 1
        assert "failure_chains" in analysis["patterns"]
    
    def test_analyze_decision_chains(self, analyzer):
        """決定チェーン分析テスト"""
        # チェーン1: autonomous -> autonomous (成功)
        flow1 = analyzer.create_flow("task_001", "Test task 1")
        analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test1",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test2",
            options=["B"],
            selected="B",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.complete_flow(flow1, overall_success=True)
        
        analysis = analyzer.analyze_decision_chains()
        
        assert analysis["total_unique_chains"] == 1
        assert "autonomous -> autonomous" in analysis["chains"]
    
    def test_detect_risk_patterns(self, analyzer):
        """リスク検出テスト"""
        # 高信頼度での失敗
        flow1 = analyzer.create_flow("task_001", "Test task 1")
        step = analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.95,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=False)
        analyzer.complete_flow(flow1, overall_success=False)
        
        # 過度なエスカレーション
        flow2 = analyzer.create_flow("task_002", "Test task 2")
        for i in range(4):
            analyzer.record_decision(
                flow=flow2,
                decision_type=DecisionType.ESCALATED,
                context=f"Test{i}",
                options=["A"],
                selected="A",
                reasoning="Test",
                confidence=0.7,
            )
        analyzer.complete_flow(flow2, overall_success=False)
        
        risks = analyzer.detect_risk_patterns()
        
        assert len(risks["high_confidence_failures"]) > 0
        assert len(risks["excessive_escalations"]) > 0
    
    def test_generate_autonomy_report(self, analyzer):
        """自律性レポート生成テスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
            user_intervention=False,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=True)
        analyzer.complete_flow(flow, overall_success=True)
        
        report = analyzer.generate_autonomy_report()
        
        assert "autonomy_score" in report
        assert "summary" in report
        assert report["autonomy_score"] >= 0.0
        assert report["autonomy_score"] <= 1.0
        assert report["summary"]["total_tasks"] == 1
    
    def test_export_to_json(self, analyzer, tmp_path):
        """JSON エクスポートテスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.complete_flow(flow, overall_success=True)
        
        output_file = tmp_path / "report.json"
        analyzer.export_to_json(output_file)
        
        assert output_file.exists()
        
        import json
        with open(output_file) as f:
            data = json.load(f)
        
        assert "autonomy_score" in data
        assert "summary" in data
    
    def test_export_flows_to_csv(self, analyzer, tmp_path):
        """フロー CSV エクスポートテスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.complete_flow(flow, overall_success=True)
        
        output_file = tmp_path / "flows.csv"
        analyzer.export_flows_to_csv(output_file)
        
        assert output_file.exists()
        
        with open(output_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 2  # ヘッダー + 1行
    
    def test_export_steps_to_csv(self, analyzer, tmp_path):
        """ステップ CSV エクスポートテスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="Test",
            options=["A"],
            selected="A",
            reasoning="Test",
            confidence=0.9,
        )
        analyzer.complete_flow(flow, overall_success=True)
        
        output_file = tmp_path / "steps.csv"
        analyzer.export_steps_to_csv(output_file)
        
        assert output_file.exists()
        
        with open(output_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 2  # ヘッダー + 1行
    
    def test_reset_analysis(self, analyzer):
        """分析リセットテスト"""
        flow = analyzer.create_flow("task_001", "Test task")
        analyzer.complete_flow(flow, overall_success=True)
        
        assert len(analyzer.flows) == 1
        
        analyzer.reset_analysis()
        
        assert len(analyzer.flows) == 0


class TestIntegration:
    """統合テスト"""
    
    def test_complete_workflow(self, tmp_path):
        """完全なワークフローテスト"""
        analyzer = DecisionAnalyzer()
        
        # タスク1: 成功ケース
        flow1 = analyzer.create_flow("search_001", "検索クエリの最適化")
        
        # ステップ1: クエリ解析
        step1 = analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="検索クエリの語彙分析",
            options=["形態素解析", "単純分割"],
            selected="形態素解析",
            reasoning="日本語最適化のため",
            confidence=0.95,
        )
        analyzer.evaluate_step_quality(step1, actual_outcome=True)
        
        # ステップ2: インデックス選択
        step2 = analyzer.record_decision(
            flow=flow1,
            decision_type=DecisionType.AUTONOMOUS,
            context="インデックスの選択",
            options=["semantic_index", "keyword_index"],
            selected="semantic_index",
            reasoning="意味検索が効果的",
            confidence=0.92,
        )
        analyzer.evaluate_step_quality(step2, actual_outcome=True)
        
        analyzer.complete_flow(flow1, overall_success=True)
        
        # タスク2: 部分失敗ケース
        flow2 = analyzer.create_flow("search_002", "検索クエリの分類")
        
        # ステップ1: 自律決定
        step3 = analyzer.record_decision(
            flow=flow2,
            decision_type=DecisionType.AUTONOMOUS,
            context="クエリ分類",
            options=["entity_search", "concept_search"],
            selected="entity_search",
            reasoning="エンティティ検出から判定",
            confidence=0.88,
        )
        analyzer.evaluate_step_quality(step3, actual_outcome=False)
        
        # ステップ2: ガイド付き決定
        step4 = analyzer.record_decision(
            flow=flow2,
            decision_type=DecisionType.GUIDED,
            context="リトライ戦略",
            options=["retry_with_expansion", "fallback_keyword"],
            selected="retry_with_expansion",
            reasoning="クエリ拡張試行",
            confidence=0.75,
            user_intervention=True,
        )
        analyzer.evaluate_step_quality(step4, actual_outcome=True)
        
        analyzer.complete_flow(flow2, overall_success=True)
        
        # レポート生成
        report = analyzer.generate_autonomy_report()
        
        assert report["summary"]["total_tasks"] == 2
        assert report["summary"]["overall_success_rate"] == 1.0
        assert report["autonomy_score"] > 0.0
        
        # エクスポート
        analyzer.export_to_json(tmp_path / "report.json")
        analyzer.export_flows_to_csv(tmp_path / "flows.csv")
        analyzer.export_steps_to_csv(tmp_path / "steps.csv")
        
        assert (tmp_path / "report.json").exists()
        assert (tmp_path / "flows.csv").exists()
        assert (tmp_path / "steps.csv").exists()
