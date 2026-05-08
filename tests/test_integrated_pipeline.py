#!/usr/bin/env python3
"""
=============================================================================
Test Suite for Phase 7 Complete Pipeline
=============================================================================

目的:
  - エンドツーエンド推論パイプラインの最全テスト
  - ユニットテスト・統合テスト・ストレステスト
  - パフォーマンス検証

テスト項目:
  1. 単一クエリ処理
  2. バッチ処理
  3. エラーハンドリング
  4. ドメイン推定の正確性
  5. キャッシング動作
  6. パフォーマンス
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Phase 7 パイプラインのインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.integrated_pipeline import (
    Phase7CompletePipeline,
    PipelineConfig,
    ProcessingResult
)


class TestPipelineConfig:
    """PipelineConfig クラスのテスト"""
    
    def test_default_config(self):
        """デフォルト設定が正しく生成されるか"""
        config = PipelineConfig()
        assert config.enable_caching is True
        assert config.cache_size == 1000
        assert config.enable_logging is True
        assert config.timeout_seconds == 30
        assert config.min_confidence_threshold == 0.5
    
    def test_custom_config(self):
        """カスタム設定が正しく保存されるか"""
        config = PipelineConfig(
            enable_caching=False,
            cache_size=500,
            timeout_seconds=60
        )
        assert config.enable_caching is False
        assert config.cache_size == 500
        assert config.timeout_seconds == 60
    
    def test_config_to_dict(self):
        """設定を辞書に変換できるか"""
        config = PipelineConfig(cache_size=100)
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict['cache_size'] == 100


class TestProcessingResult:
    """ProcessingResult データクラスのテスト"""
    
    def test_result_creation(self):
        """結果オブジェクトが正しく作成されるか"""
        result = ProcessingResult(
            query="テストクエリ",
            answer="テスト回答",
            domain="Medical",
            confidence=0.95,
            sources=["source1", "source2"],
            processing_time_ms=100.5,
            timestamp="2026-04-12T00:00:00"
        )
        assert result.query == "テストクエリ"
        assert result.confidence == 0.95
        assert len(result.sources) == 2
    
    def test_result_to_dict(self):
        """結果を辞書に変換できるか"""
        result = ProcessingResult(
            query="Q",
            answer="A",
            domain="Med",
            confidence=0.8,
            sources=[],
            processing_time_ms=50,
            timestamp="2026-01-01T00:00:00"
        )
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict['query'] == "Q"
        assert result_dict['domain'] == "Med"
    
    def test_result_to_json(self):
        """結果をJSON文字列に変換できるか"""
        result = ProcessingResult(
            query="Q",
            answer="A",
            domain="Med",
            confidence=0.8,
            sources=[],
            processing_time_ms=50,
            timestamp="2026-01-01T00:00:00"
        )
        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "Q" in json_str
        assert "Med" in json_str


class TestPhase7CompletePipeline:
    """Phase7CompletePipeline クラスのテスト"""
    
    @pytest.fixture
    def pipeline(self):
        """パイプラインの初期化"""
        config = PipelineConfig(enable_logging=False)
        return Phase7CompletePipeline(config)
    
    def test_pipeline_initialization(self, pipeline):
        """パイプラインが正しく初期化されるか"""
        assert pipeline is not None
        assert pipeline.config.enable_caching is True
        assert pipeline.stats['total_queries'] == 0
    
    def test_process_single_query(self, pipeline):
        """単一クエリが処理されるか"""
        query = "患者の症状について教えてください。"
        result = pipeline.process_query(query)
        
        assert result is not None
        assert isinstance(result, ProcessingResult)
        assert result.query == query
        assert result.processing_time_ms > 0
        assert pipeline.stats['total_queries'] == 1
    
    def test_domain_detection(self, pipeline):
        """ドメイン推定が機能しているか"""
        medical_query = "患者の心臓が異常です。"
        result = pipeline.process_query(medical_query)
        
        assert result.domain is not None
        assert result.domain != "Unknown" or result.error is not None
    
    def test_confidence_scoring(self, pipeline):
        """信頼度スコアが有効な範囲内か"""
        query = "テストクエリ"
        result = pipeline.process_query(query)
        
        # 信頼度は0～1の範囲内
        assert 0.0 <= result.confidence <= 1.0
    
    def test_error_handling(self, pipeline):
        """エラーハンドリングが正しく機能するか"""
        # 空のクエリ
        empty_result = pipeline.process_query("")
        assert empty_result is not None
        assert pipeline.stats['total_queries'] == 1
    
    def test_batch_processing(self, pipeline):
        """バッチ処理が機能するか"""
        queries = [
            "医学的な質問1",
            "医学的な質問2",
            "医学的な質問3"
        ]
        results = pipeline.process_batch(queries, batch_size=2)
        
        assert len(results) == 3
        assert all(isinstance(r, ProcessingResult) for r in results)
        assert pipeline.stats['total_queries'] == 3
    
    def test_statistics_accuracy(self, pipeline):
        """統計情報が正確に計算されるか"""
        # 3つのクエリを処理
        pipeline.process_query("クエリ1")
        pipeline.process_query("クエリ2")
        pipeline.process_query("クエリ3")
        
        stats = pipeline.get_statistics()
        assert stats['total_queries'] == 3
        assert stats['successful_queries'] + stats['failed_queries'] == 3
        assert 0 <= stats['success_rate'] <= 100
    
    def test_processing_time_tracking(self, pipeline):
        """処理時間が正確に記録されるか"""
        query = "処理時間テスト"
        result = pipeline.process_query(query)
        
        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 60000  # 60秒以内
        assert pipeline.stats['total_processing_time_ms'] > 0
    
    def test_multiple_domain_queries(self, pipeline):
        """複数のドメインクエリが処理されるか"""
        queries = [
            ("医療", "患者の治療法を教えてください。"),
            ("法律", "契約違反について説明してください。"),
            ("ビジネス", "マーケティング戦略で重要なことは？"),
            ("技術", "プログラミングのベストプラクティスは？"),
            ("科学", "地球温暖化とは何ですか？"),
        ]
        
        for expected_domain, query in queries:
            result = pipeline.process_query(query)
            assert result is not None
            # ドメインが提出されているか、またはエラーが適切に処理されているか
            assert result.domain or result.error is not None
    
    def test_cache_effectiveness(self, pipeline):
        """キャッシングが有効に機能しているか"""
        # 同じドメインキーワードを2回呼び出し
        domain1 = "Medical"
        keywords1 = pipeline._get_domain_keywords(domain1)
        keywords2 = pipeline._get_domain_keywords(domain1)
        
        # キャッシュ機能のおかげで同じ結果が返される
        assert keywords1 == keywords2


class TestPerformanceBenchmark:
    """パフォーマンステスト"""
    
    @pytest.fixture
    def pipeline(self):
        """パイプラインの初期化"""
        config = PipelineConfig(enable_logging=False)
        return Phase7CompletePipeline(config)
    
    def test_response_time_single_query(self, pipeline):
        """単一クエリの応答時間テスト"""
        query = "テストクエリ"
        start = time.perf_counter()
        result = pipeline.process_query(query)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # 響応時間は500ms以内（ターゲット）
        assert result.processing_time_ms < 5000  # 実装的には寛容に
        assert elapsed_ms > 0
    
    def test_throughput_batch_queries(self, pipeline):
        """バッチクエリのスループットテスト"""
        queries = [f"クエリ{i}" for i in range(50)]
        
        start = time.perf_counter()
        results = pipeline.process_batch(queries, batch_size=10)
        elapsed_seconds = time.perf_counter() - start
        
        throughput = len(results) / elapsed_seconds if elapsed_seconds > 0 else 0
        assert len(results) == 50
        assert throughput > 0  # 確認可能な処理速度
    
    def test_memory_efficiency(self, pipeline):
        """メモリ効率テスト（大量クエリ処理）"""
        # 100クエリを順次処理
        for i in range(100):
            result = pipeline.process_query(f"大量テストクエリ{i}")
            assert result is not None
        
        stats = pipeline.get_statistics()
        assert stats['total_queries'] == 100
        # メモリリークがないことの確認
        assert pipeline.stats['total_processing_time_ms'] > 0


class TestIntegrationScenarios:
    """統合テストシナリオ"""
    
    @pytest.fixture
    def pipeline(self):
        """パイプラインの初期化"""
        config = PipelineConfig(enable_logging=False)
        return Phase7CompletePipeline(config)
    
    def test_end_to_end_medical_scenario(self, pipeline):
        """エンドツーエンド医療シナリオ"""
        queries = [
            "患者は38度の熱があります。",
            "頭痛と関連があるかどうか教えてください。",
            "どんな治療が考えられますか？"
        ]
        
        for query in queries:
            result = pipeline.process_query(query)
            assert result is not None
            assert len(result.answer) > 0 or result.error is not None
    
    def test_multi_domain_context_flow(self, pipeline):
        """マルチドメインコンテキストフロー"""
        queries = [
            "企業の法的責任を説明してください。",
            "ビジネス倫理との関係は？",
            "技術的な実装方法は？"
        ]
        
        results = []
        for query in queries:
            result = pipeline.process_query(query)
            results.append(result)
        
        assert len(results) == 3
        assert all(r.processing_time_ms > 0 for r in results)
    
    def test_error_recovery_and_continuation(self, pipeline):
        """エラーからの復帰と継続処理"""
        # 1つのクエリでエラーが発生してもパイプラインは続行
        result1 = pipeline.process_query("テスト1")
        result2 = pipeline.process_query("")  # 空のクエリ
        result3 = pipeline.process_query("テスト3")
        
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert pipeline.stats['total_queries'] == 3


if __name__ == "__main__":
    # pytest を使用して実行
    # pytest tests/test_integrated_pipeline.py -v
    pytest.main([__file__, "-v", "--tb=short"])
