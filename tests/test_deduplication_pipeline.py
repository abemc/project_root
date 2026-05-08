"""
データ重複排除パイプラインテスト
"""

import pytest
from src.data_processing.deduplication_pipeline import (
    DataDeduplicationPipeline,
    PipelineConfig,
    PipelineMode
)


class TestDataDeduplicationPipeline:
    """DataDeduplicationPipelineテスト"""
    
    @pytest.fixture
    def pipeline(self):
        return DataDeduplicationPipeline()
    
    @pytest.fixture
    def sample_dataset(self):
        """サンプルデータセット"""
        return [
            {"id": "1", "text": "The quick brown fox", "quality": 0.8},
            {"id": "2", "text": "The quick brown fox", "quality": 0.9},  # 完全重複
            {"id": "3", "text": "A fast brown fox", "quality": 0.7},      # セマンティック類似
            {"id": "4", "text": "The cat on the mat", "quality": 0.85},
            {"id": "5", "text": "  THE  QUICK  BROWN  FOX  ", "quality": 0.75},  # 正規化後重複
            {"id": "6", "text": "The dog in the park", "quality": 0.7},
        ]
    
    # ========== 基本機能テスト ==========
    
    def test_pipeline_initialization(self):
        """パイプライン初期化テスト"""
        pipeline = DataDeduplicationPipeline()
        
        assert pipeline.config is not None
        assert pipeline.exact_deduplicator is not None
        assert pipeline.semantic_deduplicator is not None
    
    def test_pipeline_with_custom_config(self):
        """カスタム設定でのパイプライン初期化テスト"""
        config = PipelineConfig(
            mode=PipelineMode.EXACT_ONLY,
            text_field="content",
            id_field="doc_id"
        )
        pipeline = DataDeduplicationPipeline(config)
        
        assert pipeline.config.mode == PipelineMode.EXACT_ONLY
        assert pipeline.config.text_field == "content"
        assert pipeline.config.id_field == "doc_id"
    
    # ========== 処理ステップテスト ==========
    
    def test_exact_deduplication_step(self, pipeline, sample_dataset):
        """完全一致除去ステップテスト"""
        step, deduplicated_data = pipeline.process_exact_deduplication(sample_dataset)
        
        assert step.step_name == "Exact Deduplication"
        assert step.removed_count > 0
        assert len(deduplicated_data) < len(sample_dataset)
        assert step.processing_time_ms > 0
    
    def test_semantic_deduplication_step(self, pipeline, sample_dataset):
        """セマンティック除去ステップテスト"""
        step, deduplicated_data = pipeline.process_semantic_deduplication(sample_dataset)
        
        assert step.step_name == "Semantic Deduplication"
        assert step.removed_count >= 0
        assert len(deduplicated_data) > 0
        assert step.processing_time_ms > 0
    
    # ========== パイプラインモードテスト ==========
    
    def test_exact_only_mode(self, sample_dataset):
        """完全一致のみモードテスト"""
        config = PipelineConfig(mode=PipelineMode.EXACT_ONLY)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        assert result.original_count == len(sample_dataset)
        assert len(result.steps) == 1
        assert result.steps[0].step_name == "Exact Deduplication"
    
    def test_semantic_only_mode(self, sample_dataset):
        """セマンティックのみモードテスト"""
        config = PipelineConfig(mode=PipelineMode.SEMANTIC_ONLY)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        assert result.original_count == len(sample_dataset)
        assert len(result.steps) == 1
        assert result.steps[0].step_name == "Semantic Deduplication"
    
    def test_exact_then_semantic_mode(self, sample_dataset):
        """順序処理モードテスト"""
        config = PipelineConfig(mode=PipelineMode.EXACT_THEN_SEMANTIC)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        assert result.original_count == len(sample_dataset)
        assert len(result.steps) >= 1
        # 最初のステップは完全一致
        if len(result.steps) > 0:
            assert result.steps[0].step_name == "Exact Deduplication"
    
    def test_parallel_mode(self, sample_dataset):
        """並列処理モードテスト"""
        config = PipelineConfig(mode=PipelineMode.PARALLEL)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        assert result.original_count == len(sample_dataset)
        assert len(result.steps) == 2
    
    # ========== パイプライン結果テスト ==========
    
    def test_pipeline_result_structure(self, pipeline, sample_dataset):
        """パイプライン結果構造テスト"""
        result = pipeline.process(sample_dataset)
        
        assert result.original_count == len(sample_dataset)
        assert result.final_count > 0
        assert result.total_removed >= 0
        assert 0 <= result.deduplication_rate <= 100
        assert result.total_processing_time_ms > 0
        assert len(result.steps) > 0
        assert len(result.deduplicated_dataset) > 0
        assert result.config is not None
    
    def test_pipeline_removed_ids(self, pipeline, sample_dataset):
        """除去IDの追跡テスト"""
        result = pipeline.process(sample_dataset)
        
        # 除去されたIDが実際にデータセットから除去されている
        kept_ids = {item["id"] for item in result.deduplicated_dataset}
        removed_ids = set(result.all_removed_ids)
        
        assert len(kept_ids & removed_ids) == 0  # 交集合がない
        assert kept_ids | removed_ids == {"1", "2", "3", "4", "5", "6"}  # 合集合が元のIDセット
    
    # ========== ステップメトリクステスト ==========
    
    def test_step_metrics(self, pipeline, sample_dataset):
        """ステップメトリクステスト"""
        result = pipeline.process(sample_dataset)
        
        for step in result.steps:
            assert step.step_name in ["Exact Deduplication", "Semantic Deduplication"]
            assert step.duplicates_found >= 0
            assert step.removed_count >= 0
            assert len(step.removed_ids) == step.removed_count
            assert step.processing_time_ms > 0
            assert isinstance(step.metrics, dict)
    
    # ========== 品質フィールド対応テスト ==========
    
    def test_pipeline_with_quality_field(self, sample_dataset):
        """品質フィールド対応テスト"""
        config = PipelineConfig(
            quality_field="quality",
            exact_strategy="keep_best",
            semantic_strategy="keep_best"
        )
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        # 品質スコアが高いアイテムが保持される傾向
        assert result.final_count > 0
    
    # ========== レポート生成テスト ==========
    
    def test_generate_report(self, pipeline, sample_dataset):
        """レポート生成テスト"""
        result = pipeline.process(sample_dataset)
        report = pipeline.generate_pipeline_report(result)
        
        assert "データ重複排除パイプライン" in report
        assert f"{result.original_count}" in report
        assert f"{result.final_count}" in report
        assert f"{result.deduplication_rate:.2f}%" in report
        assert "✅ 完了" in report
    
    def test_report_from_last_result(self, pipeline, sample_dataset):
        """前回の結果からのレポート生成テスト"""
        pipeline.process(sample_dataset)
        
        # Noneを渡すと最後の結果を使用
        report = pipeline.generate_pipeline_report()
        
        assert "データ重複排除パイプライン" in report
        assert "✅ 完了" in report
    
    # ========== 設定テスト ==========
    
    def test_normalization_enabled(self, sample_dataset):
        """正規化有効テスト"""
        config = PipelineConfig(enable_normalization=True)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        # 正規化により正規表現パターンの重複が検出される
        assert result.total_removed > 0
    
    def test_normalization_disabled(self, sample_dataset):
        """正規化無効テスト"""
        config = PipelineConfig(enable_normalization=False)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(sample_dataset)
        
        # 正規化なしでも処理は実行される
        assert result.original_count == len(sample_dataset)
    
    # ========== エッジケーステスト ==========
    
    def test_empty_dataset(self, pipeline):
        """空データセットテスト"""
        result = pipeline.process([])
        
        assert result.original_count == 0
        assert result.final_count == 0
        assert result.total_removed == 0
    
    def test_single_item(self, pipeline):
        """単一アイテムテスト"""
        dataset = [{"id": "1", "text": "single item"}]
        result = pipeline.process(dataset)
        
        assert result.original_count == 1
        assert result.final_count == 1
        assert result.total_removed == 0
    
    def test_no_duplicates(self, pipeline):
        """重複なしテスト"""
        dataset = [
            {"id": "1", "text": "apple"},
            {"id": "2", "text": "banana"},
            {"id": "3", "text": "cherry"},
        ]
        
        result = pipeline.process(dataset)
        
        assert result.original_count == 3
        # 高い閾値なので重複なし
        assert result.final_count == 3
    
    def test_all_duplicates(self, pipeline):
        """すべて重複テスト"""
        dataset = [
            {"id": "1", "text": "same text"},
            {"id": "2", "text": "same text"},
            {"id": "3", "text": "same text"},
        ]
        
        result = pipeline.process(dataset)
        
        assert result.original_count == 3
        assert result.final_count == 1
        assert result.total_removed == 2
    
    # ========== パフォーマンステスト ==========
    
    def test_performance_large_dataset(self):
        """大規模データセットパフォーマンステスト"""
        # 500件のデータセット作成
        dataset = []
        for i in range(500):
            dataset.append({
                "id": f"id_{i}",
                "text": f"Text number {i % 50}"  # 50種類のテキスト
            })
        
        config = PipelineConfig(mode=PipelineMode.EXACT_ONLY)
        pipeline = DataDeduplicationPipeline(config)
        
        result = pipeline.process(dataset)
        
        # パフォーマンス確認
        items_per_ms = result.original_count / result.total_processing_time_ms
        assert items_per_ms > 10  # 最低10件/ms
    
    # ========== 統合テスト ==========
    
    def test_full_pipeline_workflow(self, sample_dataset):
        """完全なパイプラインワークフローテスト"""
        # 異なるモードで処理
        modes = [
            PipelineMode.EXACT_ONLY,
            PipelineMode.SEMANTIC_ONLY,
            PipelineMode.EXACT_THEN_SEMANTIC,
            PipelineMode.PARALLEL
        ]
        
        results = []
        for mode in modes:
            config = PipelineConfig(mode=mode)
            pipeline = DataDeduplicationPipeline(config)
            result = pipeline.process(sample_dataset)
            results.append(result)
        
        # すべてのモードで処理が完了
        assert len(results) == 4
        assert all(r.original_count == len(sample_dataset) for r in results)
        assert all(r.final_count > 0 for r in results)
    
    def test_result_consistency(self, sample_dataset):
        """結果の一貫性テスト"""
        config = PipelineConfig(mode=PipelineMode.EXACT_THEN_SEMANTIC)
        pipeline = DataDeduplicationPipeline(config)
        
        result1 = pipeline.process(sample_dataset)
        result2 = pipeline.process(sample_dataset)
        
        # 同じ入力に対して同じ結果
        assert result1.total_removed == result2.total_removed
        assert result1.final_count == result2.final_count
        assert set(result1.all_removed_ids) == set(result2.all_removed_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
