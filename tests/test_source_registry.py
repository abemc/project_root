"""
ソース信頼性レジストリ テスト
"""

import pytest
import tempfile
from pathlib import Path
from src.quality_assurance.source_credibility import (
    SourceCredibilityAnalyzer,
    SourceMetadata,
    AccuracyHistory
)
from src.quality_assurance.source_registry import (
    SourceRegistry
)


class TestSourceRegistry:
    """SourceRegistryテスト"""
    
    @pytest.fixture
    def temp_registry(self):
        """テンポラリレジストリ"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SourceRegistry(
                registry_path=str(Path(tmpdir) / "registry.json")
            )
            yield registry
    
    @pytest.fixture
    def sample_analysis_result(self):
        """サンプル分析結果"""
        analyzer = SourceCredibilityAnalyzer()
        metadata = SourceMetadata(
            source_id="test_source",
            domain="test.edu",
            organization="Test University"
        )
        history = AccuracyHistory(source_id="test_source")
        for _ in range(15):
            history.add_correct_claim()
        for _ in range(5):
            history.add_incorrect_claim()
        
        result = analyzer.analyze_credibility(
            "test_source",
            metadata=metadata,
            accuracy_history=history
        )
        return result
    
    def test_register_source(self, temp_registry, sample_analysis_result):
        """ソース登録テスト"""
        record = temp_registry.register_source(sample_analysis_result)
        
        assert record.source_id == "test_source"
        assert record.analysis_count == 1
        assert record.latest_credibility_score > 0
    
    def test_get_source(self, temp_registry, sample_analysis_result):
        """ソース取得テスト"""
        temp_registry.register_source(sample_analysis_result)
        
        record = temp_registry.get_source("test_source")
        
        assert record is not None
        assert record.source_id == "test_source"
    
    def test_get_nonexistent_source(self, temp_registry):
        """存在しないソース取得テスト"""
        record = temp_registry.get_source("nonexistent")
        
        assert record is None
    
    def test_get_all_sources(self, temp_registry, sample_analysis_result):
        """全ソース取得テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for i in range(3):
            result = analyzer.analyze_credibility(f"source_{i}")
            temp_registry.register_source(result)
        
        sources = temp_registry.get_all_sources()
        
        assert len(sources) == 3
    
    def test_register_with_tags(self, temp_registry, sample_analysis_result):
        """タグ付きソース登録テスト"""
        record = temp_registry.register_source(
            sample_analysis_result,
            tags=["news", "tech"],
            notes="Test source"
        )
        
        assert "news" in record.tags
        assert "tech" in record.tags
        assert record.notes == "Test source"
    
    def test_get_sources_by_tag(self, temp_registry, sample_analysis_result):
        """タグ別ソース取得テスト"""
        temp_registry.register_source(sample_analysis_result, tags=["tech"])
        
        analyzer = SourceCredibilityAnalyzer()
        result2 = analyzer.analyze_credibility("source2")
        temp_registry.register_source(result2, tags=["science"])
        
        tech_sources = temp_registry.get_sources_by_tag("tech")
        
        assert len(tech_sources) == 1
        assert tech_sources[0].source_id == "test_source"
    
    def test_flag_source(self, temp_registry, sample_analysis_result):
        """ソースフラグ設定テスト"""
        temp_registry.register_source(sample_analysis_result)
        
        result = temp_registry.flag_source(
            "test_source",
            reason="Suspicious activity detected"
        )
        
        assert result is True
        record = temp_registry.get_source("test_source")
        assert record.flagged is True
        assert "Suspicious" in record.flag_reason
    
    def test_unflag_source(self, temp_registry, sample_analysis_result):
        """ソースフラグ解除テスト"""
        temp_registry.register_source(sample_analysis_result)
        temp_registry.flag_source("test_source", reason="Test")
        
        temp_registry.flag_source("test_source", unflag=True)
        
        record = temp_registry.get_source("test_source")
        assert record.flagged is False
    
    def test_get_flagged_sources(self, temp_registry, sample_analysis_result):
        """フラグ付きソース取得テスト"""
        analyzer = SourceCredibilityAnalyzer()
        result1 = sample_analysis_result
        temp_registry.register_source(result1)
        
        result2 = analyzer.analyze_credibility("source2")
        temp_registry.register_source(result2)
        
        temp_registry.flag_source("test_source", reason="Issue 1")
        temp_registry.flag_source("source2", reason="Issue 2")
        
        flagged = temp_registry.get_flagged_sources()
        
        assert len(flagged) == 2
    
    def test_score_trend(self, temp_registry):
        """スコアトレンドテスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        # 複数回の分析を登録
        for i in range(3):
            result = analyzer.analyze_credibility("trend_test")
            temp_registry.register_source(result)
        
        trend = temp_registry.get_score_trend("trend_test")
        
        assert trend is not None
        assert len(trend) == 3
    
    def test_average_score(self, temp_registry):
        """平均スコア計算テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for _ in range(3):
            result = analyzer.analyze_credibility("avg_test")
            temp_registry.register_source(result)
        
        avg = temp_registry.get_average_score("avg_test")
        
        assert avg is not None
        assert 0.0 <= avg <= 1.0
    
    def test_score_stability(self, temp_registry):
        """スコア安定性計算テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for _ in range(5):
            result = analyzer.analyze_credibility("stable_test")
            temp_registry.register_source(result)
        
        stability = temp_registry.get_score_stability("stable_test")
        
        # 安定したスコアは低い標準偏差
        assert stability is not None
        assert stability >= 0.0
    
    def test_get_statistics(self, temp_registry, sample_analysis_result):
        """統計情報取得テスト"""
        temp_registry.register_source(sample_analysis_result)
        
        stats = temp_registry.get_statistics()
        
        assert stats.total_sources == 1
        assert stats.average_credibility_score > 0
        assert stats.total_records == 1
    
    def test_get_top_sources(self, temp_registry):
        """上位ソース取得テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for i in range(5):
            result = analyzer.analyze_credibility(f"source_{i}")
            temp_registry.register_source(result)
        
        top = temp_registry.get_top_sources(3)
        
        assert len(top) <= 3
        # スコアが降順になっているか確認
        for i in range(len(top) - 1):
            assert top[i][1] >= top[i + 1][1]
    
    def test_get_bottom_sources(self, temp_registry):
        """下位ソース取得テスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for i in range(5):
            result = analyzer.analyze_credibility(f"source_{i}")
            temp_registry.register_source(result)
        
        bottom = temp_registry.get_bottom_sources(3)
        
        assert len(bottom) <= 3
        # スコアが昇順になっているか確認
        for i in range(len(bottom) - 1):
            assert bottom[i][1] <= bottom[i + 1][1]
    
    def test_export_registry(self, temp_registry, sample_analysis_result):
        """レジストリエクスポートテスト"""
        temp_registry.register_source(sample_analysis_result)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = str(Path(tmpdir) / "export.json")
            result = temp_registry.export_registry(export_path)
            
            assert result is True
            assert Path(export_path).exists()
    
    def test_import_registry(self, temp_registry, sample_analysis_result):
        """レジストリインポートテスト"""
        # 最初のレジストリに登録
        temp_registry.register_source(sample_analysis_result)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = str(Path(tmpdir) / "export.json")
            temp_registry.export_registry(export_path)
            
            # 新しいレジストリにインポート
            new_registry = SourceRegistry(
                registry_path=str(Path(tmpdir) / "new_registry.json")
            )
            result = new_registry.import_registry(export_path)
            
            assert result is True
            assert new_registry.get_source("test_source") is not None
    
    def test_delete_source(self, temp_registry, sample_analysis_result):
        """ソース削除テスト"""
        temp_registry.register_source(sample_analysis_result)
        
        result = temp_registry.delete_source("test_source")
        
        assert result is True
        assert temp_registry.get_source("test_source") is None
    
    def test_delete_nonexistent_source(self, temp_registry):
        """存在しないソース削除テスト"""
        result = temp_registry.delete_source("nonexistent")
        
        assert result is False
    
    def test_clear_registry(self, temp_registry, sample_analysis_result):
        """レジストリクリアテスト"""
        analyzer = SourceCredibilityAnalyzer()
        
        for i in range(3):
            result = analyzer.analyze_credibility(f"source_{i}")
            temp_registry.register_source(result)
        
        result = temp_registry.clear_registry()
        
        assert result is True
        assert len(temp_registry.get_all_sources()) == 0
    
    def test_generate_report(self, temp_registry, sample_analysis_result):
        """レジストリレポート生成テスト"""
        temp_registry.register_source(sample_analysis_result)
        
        report = temp_registry.generate_report()
        
        assert "SOURCE REGISTRY REPORT" in report
        assert "test_source" in report or "Total Sources" in report
    
    def test_persistence(self):
        """永続性テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = str(Path(tmpdir) / "registry.json")
            
            # 最初のレジストリに登録
            registry1 = SourceRegistry(registry_path=registry_path)
            analyzer = SourceCredibilityAnalyzer()
            result = analyzer.analyze_credibility("persistent_source")
            registry1.register_source(result)
            
            # 新しいレジストリで読み込み
            registry2 = SourceRegistry(registry_path=registry_path)
            
            assert registry2.get_source("persistent_source") is not None
            assert len(registry2.get_all_sources()) == 1


class TestSourceRegistryEdgeCases:
    """エッジケーステスト"""
    
    def test_empty_registry_statistics(self):
        """空のレジストリ統計テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SourceRegistry(
                registry_path=str(Path(tmpdir) / "registry.json")
            )
            stats = registry.get_statistics()
            
            assert stats.total_sources == 0
            assert stats.average_credibility_score == 0.0
    
    def test_large_registry(self):
        """大規模レジストリテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SourceRegistry(
                registry_path=str(Path(tmpdir) / "registry.json")
            )
            analyzer = SourceCredibilityAnalyzer()
            
            # 100個のソースを登録
            for i in range(100):
                result = analyzer.analyze_credibility(f"source_{i}")
                registry.register_source(result)
            
            assert len(registry.get_all_sources()) == 100
            stats = registry.get_statistics()
            assert stats.total_sources == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
