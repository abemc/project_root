"""
信頼性スコア更新エンジン テスト
"""

import pytest
from datetime import datetime, timedelta
from src.quality_assurance.credibility_updater import (
    CredibilityScoreUpdater,
    UpdateReason,
    AlertLevel
)


class TestCredibilityScoreUpdater:
    """CredibilityScoreUpdaterテスト"""
    
    @pytest.fixture
    def updater(self):
        return CredibilityScoreUpdater(sensitivity=0.5)
    
    def test_verification_passed_update(self, updater):
        """検証成功時の更新テスト"""
        update = updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=True,
            confidence=1.0
        )
        
        assert update.source_id == "test_source"
        assert update.old_score == 0.7
        assert update.new_score > update.old_score
        assert update.update_reason == UpdateReason.VERIFICATION_PASSED
    
    def test_verification_failed_update(self, updater):
        """検証失敗時の更新テスト"""
        update = updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=False,
            confidence=1.0
        )
        
        assert update.new_score < update.old_score
        assert update.update_reason == UpdateReason.VERIFICATION_FAILED
    
    def test_update_with_accuracy_rate(self, updater):
        """精度率を考慮した更新テスト"""
        update = updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=True,
            accuracy_rate=0.95
        )
        
        assert update.new_score > 0.7
    
    def test_update_with_low_accuracy_rate(self, updater):
        """低精度率時の更新テスト"""
        update = updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=False,
            accuracy_rate=0.3
        )
        
        assert update.new_score < 0.7
    
    def test_correction_update(self, updater):
        """修正に基づく更新テスト"""
        update = updater.update_score_on_correction(
            source_id="test_source",
            current_score=0.8,
            correction_type="critical"
        )
        
        assert update.new_score < update.old_score
        assert update.update_reason == UpdateReason.CORRECTION_PUBLISHED
    
    def test_retraction_update(self, updater):
        """撤回に基づく更新テスト"""
        update = updater.update_score_on_retraction(
            source_id="test_source",
            current_score=0.8,
            retraction_severity="severe"
        )
        
        assert update.new_score < update.old_score
        assert update.update_reason == UpdateReason.RETRACTION_ISSUED
    
    def test_accuracy_trend_improving(self, updater):
        """精度トレンド改善時の更新テスト"""
        update = updater.update_score_on_accuracy_trend(
            source_id="test_source",
            current_score=0.6,
            trend="improving",
            trend_strength=0.8
        )
        
        assert update.new_score > update.old_score
        assert update.update_reason == UpdateReason.ACCURACY_IMPROVEMENT
    
    def test_accuracy_trend_declining(self, updater):
        """精度トレンド悪化時の更新テスト"""
        update = updater.update_score_on_accuracy_trend(
            source_id="test_source",
            current_score=0.8,
            trend="declining",
            trend_strength=0.8
        )
        
        assert update.new_score < update.old_score
        assert update.update_reason == UpdateReason.ACCURACY_DECLINE
    
    def test_manual_adjustment(self, updater):
        """手動調整テスト"""
        update = updater.apply_manual_adjustment(
            source_id="test_source",
            current_score=0.7,
            adjustment=0.05,
            reason="Review by expert"
        )
        
        assert update.score_change > 0
        assert update.update_reason == UpdateReason.MANUAL_ADJUSTMENT
    
    def test_score_bounds(self, updater):
        """スコア範囲制限テスト"""
        # 0を下回らないことを確認
        update = updater.update_score_on_retraction(
            source_id="test_source",
            current_score=0.1,
            retraction_severity="severe"
        )
        assert update.new_score >= 0.0
        
        # 1を超えないことを確認
        update = updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.9,
            verification_passed=True,
            confidence=1.0,
            accuracy_rate=1.0
        )
        assert update.new_score <= 1.0
    
    def test_confidence_impact(self, updater):
        """信頼度の影響テスト"""
        update_high_conf = updater.update_score_on_verification(
            source_id="test1",
            current_score=0.7,
            verification_passed=True,
            confidence=1.0
        )
        
        update_low_conf = updater.update_score_on_verification(
            source_id="test2",
            current_score=0.7,
            verification_passed=True,
            confidence=0.3
        )
        
        # 信頼度が高い方がスコア変化が大きい
        assert abs(update_high_conf.score_change) > abs(update_low_conf.score_change)
    
    def test_alert_generation_critical(self):
        """重大アラート生成テスト"""
        updater = CredibilityScoreUpdater(sensitivity=1.0)  # 高感度で確実に生成
        updater.update_score_on_retraction(
            source_id="test_source",
            current_score=0.9,  # 高い初期スコア
            retraction_severity="severe"
        )
        
        alerts = updater.get_active_alerts()
        critical_alerts = [a for a in alerts if a.alert_level == AlertLevel.CRITICAL]
        
        assert len(critical_alerts) > 0
    
    def test_alert_generation_warning(self, updater):
        """警告アラート生成テスト"""
        updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=False
        )
        
        alerts = updater.get_active_alerts()
        warning_alerts = [a for a in alerts if a.alert_level == AlertLevel.WARNING]
        
        assert len(warning_alerts) > 0
    
    def test_low_score_alert(self, updater):
        """低スコアアラートテスト"""
        updater.update_score_on_retraction(
            source_id="test_source",
            current_score=0.5,
            retraction_severity="severe"
        )
        
        alerts = updater.get_active_alerts()
        
        # 低スコアアラートがあるはず
        assert len(alerts) > 0
    
    def test_get_update_history(self, updater):
        """更新履歴取得テスト"""
        updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=True
        )
        updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.75,
            verification_passed=False
        )
        
        history = updater.get_update_history(source_id="test_source")
        
        assert len(history) == 2
        # 最新の更新が最初に来る
        assert history[0].score_change < 0
    
    def test_score_trend_analysis(self, updater):
        """スコアトレンド分析テスト"""
        for _ in range(3):
            updater.update_score_on_accuracy_trend(
                source_id="trend_test",
                current_score=0.7,
                trend="improving",
                trend_strength=0.5
            )
        
        analysis = updater.get_score_trend_analysis(
            source_id="trend_test",
            window_days=30
        )
        
        assert analysis["updates_count"] == 3
        assert analysis["trend"] == "improving"
        assert analysis["average_change"] > 0
    
    def test_statistics(self, updater):
        """統計情報取得テスト"""
        updater.update_score_on_verification(
            source_id="source1",
            current_score=0.7,
            verification_passed=True
        )
        updater.update_score_on_verification(
            source_id="source2",
            current_score=0.8,
            verification_passed=False
        )
        
        stats = updater.get_statistics()
        
        assert stats.total_updates == 2
        assert stats.sources_improved == 1
        assert stats.sources_declined == 1
    
    def test_address_alert(self, updater):
        """アラート対応テスト"""
        updater.update_score_on_retraction(
            source_id="test_source",
            current_score=0.8,
            retraction_severity="severe"
        )
        
        alerts = updater.get_active_alerts()
        initial_count = len(alerts)
        
        if alerts:
            updater.address_alert(0, "Issue has been resolved")
            remaining_alerts = len(updater.get_active_alerts())
            
            assert remaining_alerts < initial_count
    
    def test_generate_report(self, updater):
        """レポート生成テスト"""
        updater.update_score_on_verification(
            source_id="test_source",
            current_score=0.7,
            verification_passed=True
        )
        
        report = updater.generate_report()
        
        assert "CREDIBILITY SCORE UPDATER REPORT" in report
        assert "Total Updates" in report
        assert "1" in report  # 1つの更新


class TestCredibilityScoreUpdaterSensitivity:
    """感度設定テスト"""
    
    def test_high_sensitivity(self):
        """高感度設定テスト"""
        updater = CredibilityScoreUpdater(sensitivity=0.9)
        
        update = updater.update_score_on_verification(
            source_id="test",
            current_score=0.7,
            verification_passed=True,
            confidence=1.0
        )
        
        assert abs(update.score_change) > 0.02  # 大きな変更
    
    def test_low_sensitivity(self):
        """低感度設定テスト"""
        updater = CredibilityScoreUpdater(sensitivity=0.1)
        
        update = updater.update_score_on_verification(
            source_id="test",
            current_score=0.7,
            verification_passed=True,
            confidence=1.0
        )
        
        assert abs(update.score_change) < 0.01  # 小さな変更


class TestCredibilityScoreUpdaterEdgeCases:
    """エッジケーステスト"""
    
    def test_empty_history(self):
        """空の履歴テスト"""
        updater = CredibilityScoreUpdater()
        
        history = updater.get_update_history()
        
        assert len(history) == 0
    
    def test_multiple_sources(self):
        """複数ソーステスト"""
        updater = CredibilityScoreUpdater()
        
        for i in range(10):
            updater.update_score_on_verification(
                source_id=f"source_{i}",
                current_score=0.7,
                verification_passed=True
            )
        
        stats = updater.get_statistics()
        
        assert stats.total_updates == 10
        assert stats.sources_improved == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
