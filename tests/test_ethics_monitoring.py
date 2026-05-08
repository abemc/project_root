"""
継続的倫理監視テストスイート

ギャップ2: 倫理監視エンジンの実装テスト
"""

import pytest
from datetime import datetime, timedelta
from src.ethics.ethics_monitor import (
    EthicsMonitor,
    BiasDetector,
    TransparencyChecker,
    FairnessMetricsCalculator,
    BiasType,
    TransparencyLevel,
    EthicsStatus,
)


class TestBiasDetector:
    """バイアス検出テスト"""

    def test_detect_gender_bias(self):
        """ジェンダーバイアス検出テスト"""
        detector = BiasDetector()

        response = "プログラマーは男性だけができる仕事である"

        results = detector.detect_bias_in_response(response)

        # ジェンダーバイアスが検出されるはず
        gender_bias = next(
            (r for r in results if r.bias_type == BiasType.GENDER),
            None
        )

        assert gender_bias is not None
        assert gender_bias.detected is True

    def test_detect_no_bias(self):
        """バイアスなし検出テスト"""
        detector = BiasDetector()

        response = "プログラミングは、スキルと経験を持つすべての人ができます。"

        results = detector.detect_bias_in_response(response)

        # バイアスが検出されないはず
        high_severity = [r for r in results if r.detected and r.severity > 0.5]

        assert len(high_severity) == 0

    def test_detect_racial_bias(self):
        """人種バイアス検出テスト"""
        detector = BiasDetector()

        response = "アジア人は数学が得意である"

        results = detector.detect_bias_in_response(response)

        # レーステストは実装のため、結果をチェック
        assert results is not None
        assert len(results) > 0

    def test_bias_severity_calculation(self):
        """バイアス重大度計算テスト"""
        detector = BiasDetector()

        response = "女性は仕事ができない。女性は家にいるべき。女性は弱い。"

        results = detector.detect_bias_in_response(response)

        gender_bias = next(
            (r for r in results if r.bias_type == BiasType.GENDER),
            None
        )

        assert gender_bias is not None
        assert gender_bias.severity > 0.3  # 高い重大度


class TestTransparencyChecker:
    """透明性チェッカーテスト"""

    def test_fully_transparent_response(self):
        """完全透明な応答テスト"""
        checker = TransparencyChecker()

        response = (
            "この質問に対する回答は以下の通りです。"
            "理由は、研究によると...。"
            "出典は厚生労働省です。"
            "ただし、この情報は2025年のデータに基づいているため、"
            "最新情報は確認推奨です。"
            "確度は約90%です。"
        )

        assessment = checker.assess_transparency(response, {"response_id": "test_1"})

        assert assessment.score >= 0.7
        assert assessment.level in [
            TransparencyLevel.FULLY_TRANSPARENT,
            TransparencyLevel.MOSTLY_TRANSPARENT
        ]

    def test_opaque_response(self):
        """不透明な応答テスト"""
        checker = TransparencyChecker()

        response = "答えはイエスです。"

        assessment = checker.assess_transparency(response, {"response_id": "test_2"})

        assert assessment.score < 0.5
        assert assessment.level == TransparencyLevel.OPAQUE

    def test_check_reasoning(self):
        """推論チェックテスト"""
        checker = TransparencyChecker()

        response_with_reasoning = "理由は、以下のとおりです。"
        response_without_reasoning = "それはそうです。"

        assert checker._check_reasoning(response_with_reasoning) is True
        assert checker._check_reasoning(response_without_reasoning) is False

    def test_check_source_citations(self):
        """出典引用チェックテスト"""
        checker = TransparencyChecker()

        response_with_source = "出典によると、..."
        response_without_source = "一般的には、..."

        assert checker._check_source_citations(response_with_source) is True
        assert checker._check_source_citations(response_without_source) is False


class TestFairnessMetricsCalculator:
    """フェアネスメトリクス計算テスト"""

    def test_calculate_fairness_metrics_balanced(self):
        """バランスの取れたフェアネスメトリクステスト"""
        calculator = FairnessMetricsCalculator()

        predictions = ["A", "B", "A", "B", "A", "B"]
        ground_truth = ["A", "B", "A", "B", "A", "B"]

        demographic_groups = {
            "group_1": [0, 1, 2],
            "group_2": [3, 4, 5],
        }

        metrics = calculator.calculate_fairness_metrics(
            predictions, ground_truth, demographic_groups
        )

        # 精度が1.0である（完全一致）
        accuracy_metric = next(
            (m for m in metrics if m.metric_name == "overall_accuracy"),
            None
        )

        assert accuracy_metric is not None
        assert accuracy_metric.value == 1.0
        assert accuracy_metric.compliant is True

    def test_calculate_fairness_metrics_imbalanced(self):
        """アンバランスなフェアネスメトリクステスト"""
        calculator = FairnessMetricsCalculator()

        predictions = ["A", "B", "B", "B", "A", "B"]
        ground_truth = ["A", "B", "A", "B", "A", "B"]

        demographic_groups = {
            "group_1": [0, 1, 2],
            "group_2": [3, 4, 5],
        }

        metrics = calculator.calculate_fairness_metrics(
            predictions, ground_truth, demographic_groups
        )

        # グループ別精度が異なるはず
        group_metrics = [m for m in metrics if "accuracy_" in m.metric_name]

        assert len(group_metrics) >= 2


class TestEthicsMonitor:
    """倫理監視エンジンテスト"""

    def test_audit_response_pass(self):
        """応答監査テスト（合格）"""
        monitor = EthicsMonitor()

        response = (
            "この質問に対する回答は、研究に基づいています。"
            "出典は信頼できる情報源です。"
            "ただし、完全性は保証されません。"
            "確度は約85%です。"
        )

        audit_log = monitor.audit_response(
            response_id="test_1",
            response=response,
        )

        assert audit_log.status == EthicsStatus.PASS
        assert audit_log.overall_score > 0.5

    def test_audit_response_with_bias(self):
        """バイアス付き応答監査テスト"""
        monitor = EthicsMonitor()

        response = "男性プログラマーが女性プログラマーより優れています。"

        audit_log = monitor.audit_response(
            response_id="test_2",
            response=response,
        )

        # バイアスが検出されるはず
        assert len(audit_log.bias_results) > 0

        # バイアス検出済みのものがあるはず
        detected_bias = [b for b in audit_log.bias_results if b.detected]
        assert len(detected_bias) > 0

    def test_audit_response_low_transparency(self):
        """低透明性応答監査テスト"""
        monitor = EthicsMonitor()

        response = "はい。"

        audit_log = monitor.audit_response(
            response_id="test_3",
            response=response,
        )

        assert audit_log.transparency.score < 0.5

    def test_audit_model_performance(self):
        """モデルパフォーマンス監査テスト"""
        monitor = EthicsMonitor()

        predictions = ["A", "B", "A", "B", "A", "B"]
        ground_truth = ["A", "B", "A", "B", "A", "B"]

        demographic_groups = {
            "group_1": [0, 1, 2],
            "group_2": [3, 4, 5],
        }

        result = monitor.audit_model_performance(
            model_id="test_model",
            predictions=predictions,
            ground_truth=ground_truth,
            demographic_groups=demographic_groups,
        )

        assert result["status"] == EthicsStatus.PASS
        assert result["compliance_rate"] >= 0.8

    def test_get_ethics_report(self):
        """倫理レポート生成テスト"""
        monitor = EthicsMonitor()

        # 複数の応答を監査
        for i in range(3):
            monitor.audit_response(
                response_id=f"test_{i}",
                response="良い応答です。" * i,
            )

        report = monitor.get_ethics_report(time_period_hours=24)

        assert report["total_audits"] >= 3
        assert "average_ethics_score" in report
        assert "pass_rate" in report

    def test_export_audit_logs(self):
        """監査ログエクスポートテスト"""
        monitor = EthicsMonitor()

        monitor.audit_response("test_1", "応答1")
        monitor.audit_response("test_2", "応答2")

        export = monitor.export_audit_logs()

        assert export["total_logs"] >= 2
        assert "logs" in export
        assert len(export["logs"]) >= 2

    def test_reset_audit_logs(self):
        """監査ログリセットテスト"""
        monitor = EthicsMonitor()

        monitor.audit_response("test_1", "応答1")
        assert len(monitor.audit_logs) >= 1

        monitor.reset_audit_logs()
        assert len(monitor.audit_logs) == 0


class TestIntegration:
    """統合テスト"""

    def test_full_ethics_monitoring_workflow(self):
        """完全な倫理監視ワークフロー"""
        monitor = EthicsMonitor()

        # ステップ1: 複数の応答を監査
        responses = [
            {
                "id": "resp_1",
                "text": "この情報は信頼できる出典に基づいています。確度は90%です。",
                "expected_status": EthicsStatus.PASS,
            },
            {
                "id": "resp_2",
                "text": "女性は数学が得意ではありません。",
                "expected_status": EthicsStatus.WARNING,
            },
        ]

        for resp in responses:
            audit_log = monitor.audit_response(
                response_id=resp["id"],
                response=resp["text"],
            )

            if resp["expected_status"] == EthicsStatus.PASS:
                assert audit_log.status in [EthicsStatus.PASS, EthicsStatus.WARNING]
            else:
                # バイアス応答は警告以上
                assert audit_log.status in [EthicsStatus.WARNING, EthicsStatus.FAIL]

        # ステップ2: 倫理レポート生成
        report = monitor.get_ethics_report(time_period_hours=24)

        assert report["total_audits"] >= 2

    def test_model_fairness_audit_workflow(self):
        """モデルフェアネス監査ワークフロー"""
        monitor = EthicsMonitor()

        # グループ1とグループ2で異なるパフォーマンス
        predictions = [
            "A", "A", "A", "A", "A",  # グループ1
            "B", "B", "B", "B", "B",  # グループ2
        ]
        ground_truth = [
            "A", "A", "A", "A", "A",
            "B", "B", "B", "B", "B",
        ]

        demographic_groups = {
            "group_1": [0, 1, 2, 3, 4],
            "group_2": [5, 6, 7, 8, 9],
        }

        result = monitor.audit_model_performance(
            model_id="perfect_model",
            predictions=predictions,
            ground_truth=ground_truth,
            demographic_groups=demographic_groups,
        )

        assert result["compliance_rate"] >= 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
