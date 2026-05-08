"""
時系列検証テストスイート

ギャップ1: 時系列検証ロジックの実装テスト
"""

import pytest
from datetime import datetime, timedelta
from src.factuality.temporal_verifier import (
    TemporalVerifier,
    FactWithTimestamp,
    FreshnessLevel,
    TemporalConsistency,
)


class TestFreshnessLevel:
    """鮮度度レベル判定テスト"""
    
    def test_very_recent_fact(self):
        """24時間以内のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(hours=12),
        )
        
        freshness = fact.get_freshness_level(now)
        assert freshness == FreshnessLevel.VERY_RECENT
    
    def test_recent_fact(self):
        """1週間以内のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=3),
        )
        
        freshness = fact.get_freshness_level(now)
        assert freshness == FreshnessLevel.RECENT
    
    def test_current_fact(self):
        """1ヶ月以内のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=15),
        )
        
        freshness = fact.get_freshness_level(now)
        assert freshness == FreshnessLevel.CURRENT
    
    def test_aged_fact(self):
        """3ヶ月以内のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=60),
        )
        
        freshness = fact.get_freshness_level(now)
        assert freshness == FreshnessLevel.AGED
    
    def test_outdated_fact(self):
        """3ヶ月以上前のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=200),
        )
        
        freshness = fact.get_freshness_level(now)
        assert freshness == FreshnessLevel.OUTDATED


class TestValidityPeriod:
    """有効期間テスト"""
    
    def test_fact_within_validity_period(self):
        """有効期間内のファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=30),
            validity_period=timedelta(days=365),
        )
        
        assert fact.is_still_valid(now) is True
    
    def test_fact_after_validity_period(self):
        """有効期間を過ぎたファクト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=400),
            validity_period=timedelta(days=365),
        )
        
        assert fact.is_still_valid(now) is False
    
    def test_fact_without_validity_period(self):
        """有効期間なしのファクト（無期限）"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テストクレーム",
            assertion_date=now - timedelta(days=1000),
            validity_period=None,
        )
        
        assert fact.is_still_valid(now) is True


class TestTemporalVerifier:
    """時系列検証エンジンのテスト"""
    
    def test_register_fact(self):
        """ファクト登録テスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        fact = verifier.register_fact(
            fact_id="weather_2026_04_20",
            claim="気温は25度である",
            assertion_date=now,
            source="気象庁",
            confidence=0.95,
        )
        
        assert fact.fact_id == "weather_2026_04_20"
        assert fact.claim == "気温は25度である"
        assert fact.confidence == 0.95
    
    def test_fact_timeline(self):
        """ファクト更新履歴テスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        # 初期クレーム
        verifier.register_fact(
            fact_id="gdp_2025",
            claim="GDP成長率は3%である",
            assertion_date=now,
            confidence=0.9,
        )
        
        # 更新版
        verifier.update_fact(
            fact_id="gdp_2025",
            new_claim="GDP成長率は3.5%である",
            current_date=now + timedelta(days=1),
            confidence=0.92,
        )
        
        timeline = verifier.get_fact_timeline("gdp_2025")
        assert len(timeline) == 2
        assert timeline[0]["claim"] == "GDP成長率は3%である"
        assert timeline[1]["claim"] == "GDP成長率は3.5%である"
    
    def test_consistency_fully_consistent(self):
        """完全一貫性テスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        # 同じクレームを複数回登録
        verifier.register_fact(
            fact_id="fact_1",
            claim="東京の首都である",
            assertion_date=now,
            confidence=0.95,
        )
        
        verifier.update_fact(
            fact_id="fact_1",
            new_claim="東京の首都である",
            current_date=now + timedelta(days=1),
            confidence=0.95,
        )
        
        record = verifier.fact_database["fact_1"]
        consistency = record.get_temporal_consistency()
        assert consistency == TemporalConsistency.FULLY_CONSISTENT
    
    def test_validity_score(self):
        """妥当性スコアテスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        verifier.register_fact(
            fact_id="fact_recent",
            claim="最近の情報",
            assertion_date=now - timedelta(hours=6),
            confidence=0.9,
        )
        
        is_valid, score = verifier.verify_fact_validity("fact_recent", now)
        assert is_valid is True
        assert score > 0.7  # 高スコア
    
    def test_outdated_fact_score(self):
        """古いファクトのスコアテスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        verifier.register_fact(
            fact_id="fact_old",
            claim="古い情報",
            assertion_date=now - timedelta(days=200),
            confidence=0.9,
        )
        
        is_valid, score = verifier.verify_fact_validity("fact_old", now)
        assert is_valid is True  # 有効だが低スコア
        assert score < 0.8  # 高信頼度でも古いファクトは低スコア
    
    def test_temporal_conflicts_detection(self):
        """時系列矛盾検出テスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        # 矛盾するクレーム
        verifier.register_fact(
            fact_id="population_2025",
            claim="日本の人口は1億である",
            assertion_date=now,
            confidence=0.9,
        )
        
        verifier.register_fact(
            fact_id="population_2025_v2",
            claim="日本の人口は1.2億である",
            assertion_date=now + timedelta(days=1),
            confidence=0.92,
        )
        
        conflicts = verifier.detect_temporal_conflicts(
            ["population_2025", "population_2025_v2"]
        )
        
        # 異なるクレームが矛盾として検出される
        assert len(conflicts) > 0
    
    def test_database_health_report(self):
        """データベース健全性レポートテスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        # 3つのファクトを登録
        verifier.register_fact("fact_1", "クレーム1", now, confidence=0.9)
        verifier.register_fact(
            "fact_2",
            "クレーム2",
            now - timedelta(days=60),
            confidence=0.85,
        )
        verifier.register_fact(
            "fact_3",
            "クレーム3",
            now - timedelta(days=200),
            confidence=0.8,
        )
        
        health = verifier.get_database_health(now)
        assert health["total_facts"] == 3
        assert health["valid_facts"] >= 1
        assert health["average_score"] > 0.0
    
    def test_verification_report(self):
        """検証レポート生成テスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        verifier.register_fact(
            fact_id="test_fact",
            claim="テストクレーム",
            assertion_date=now,
            confidence=0.9,
        )
        
        report = verifier.get_verification_report("test_fact", now)
        
        assert report["fact_id"] == "test_fact"
        assert report["latest_claim"] == "テストクレーム"
        assert report["is_valid"] is True
        assert "validity_score" in report
        assert "freshness" in report
        assert "consistency" in report
    
    def test_fact_age_calculation(self):
        """ファクト経過日数計算テスト"""
        now = datetime.now()
        fact = FactWithTimestamp(
            fact_id="fact_1",
            claim="テスト",
            assertion_date=now - timedelta(days=10),
        )
        
        age = fact.get_age_days(now)
        assert age == 10
    
    def test_export_database(self):
        """データベースエクスポートテスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        verifier.register_fact("fact_1", "クレーム1", now, confidence=0.9)
        verifier.register_fact("fact_2", "クレーム2", now, confidence=0.85)
        
        export = verifier.export_database()
        
        assert "fact_1" in export
        assert "fact_2" in export
        assert len(export) == 2
    
    def test_reset_database(self):
        """データベースリセットテスト"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        verifier.register_fact("fact_1", "クレーム1", now)
        assert len(verifier.fact_database) == 1
        
        verifier.reset_database()
        assert len(verifier.fact_database) == 0


class TestIntegration:
    """統合テスト"""
    
    def test_full_temporal_verification_workflow(self):
        """完全な時系列検証ワークフロー"""
        verifier = TemporalVerifier()
        now = datetime.now()
        
        # 1. 初期登録
        verifier.register_fact(
            fact_id="covid_cases",
            claim="日本の新規感染者は1000人である",
            assertion_date=now - timedelta(days=30),
            validity_period=timedelta(days=30),
            source="厚生労働省",
            confidence=0.95,
        )
        
        # 2. 更新
        verifier.update_fact(
            fact_id="covid_cases",
            new_claim="日本の新規感染者は500人である",
            current_date=now,
            source="厚生労働省",
            confidence=0.96,
        )
        
        # 3. 検証
        is_valid, score = verifier.verify_fact_validity("covid_cases", now)
        
        # 4. レポート生成
        report = verifier.get_verification_report("covid_cases", now)
        
        # 5. 検証
        assert is_valid is True
        assert score > 0.0
        assert report["consistency"] in [
            c.value for c in TemporalConsistency
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
