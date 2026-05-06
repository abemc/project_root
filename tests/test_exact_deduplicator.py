"""
データ重複排除システムテスト
- ExactDeduplicatorの全機能テスト
"""

import pytest
import json
from datetime import datetime
from src.data_processing.deduplicator import (
    ExactDeduplicator,
    DuplicateType,
    DeduplicationStrategy,
    DeduplicationResult
)


class TestExactDeduplicator:
    """ExactDeduplicatorテスト"""
    
    @pytest.fixture
    def deduplicator(self):
        return ExactDeduplicator()
    
    @pytest.fixture
    def sample_texts(self):
        """サンプルテキスト"""
        return [
            ("id1", "Python is a programming language"),
            ("id2", "Python is a programming language"),  # 完全重複
            ("id3", "Java is also a programming language"),
            ("id4", "Python is a programming language"),  # 完全重複
            ("id5", "C++ is a compiled language"),
        ]
    
    @pytest.fixture
    def sample_dataset(self):
        """サンプルデータセット"""
        return [
            {"id": "doc1", "text": "Natural language processing is important", "quality": 0.8},
            {"id": "doc2", "text": "Natural language processing is important", "quality": 0.9},  # 重複（品質高）
            {"id": "doc3", "text": "Machine learning is powerful", "quality": 0.7},
            {"id": "doc4", "text": "Natural language processing is important", "quality": 0.6},  # 重複
            {"id": "doc5", "text": "Deep learning is advanced", "quality": 0.8},
        ]
    
    # ========== 基本機能テスト ==========
    
    def test_hash_text(self, deduplicator):
        """テキストハッシュ計算テスト"""
        text = "test text"
        hash1 = deduplicator._hash_text(text)
        hash2 = deduplicator._hash_text(text)
        
        # 同じテキストは同じハッシュ
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5は32文字
    
    def test_normalize_text(self, deduplicator):
        """テキスト正規化テスト"""
        text1 = "  Hello   World  "
        text2 = "hello\tworld"
        text3 = "HELLO　WORLD"
        
        norm1 = deduplicator._normalize_text(text1)
        norm2 = deduplicator._normalize_text(text2)
        norm3 = deduplicator._normalize_text(text3)
        
        # すべて同じに正規化される
        assert norm1 == norm2 == norm3 == "hello world"
    
    def test_detect_exact_duplicates(self, deduplicator, sample_texts):
        """完全重複検出テスト"""
        duplicates = deduplicator.detect_exact_duplicates(sample_texts)
        
        # 1つの重複グループが検出される（3件）
        assert len(duplicates) == 1
        
        # グループには3つのIDが含まれる
        group = list(duplicates.values())[0]
        assert len(group) == 3
        assert set(group) == {"id1", "id2", "id4"}
    
    def test_detect_normalized_duplicates(self, deduplicator):
        """正規化後重複検出テスト"""
        texts = [
            ("id1", "  HELLO  WORLD  "),
            ("id2", "hello\tworld"),  # 正規化後に重複
            ("id3", "goodbye world"),
        ]
        
        duplicates = deduplicator.detect_normalized_duplicates(texts)
        
        # 1つの重複グループ
        assert len(duplicates) == 1
        group = list(duplicates.values())[0]
        assert len(group) == 2
        assert set(group) == {"id1", "id2"}
    
    # ========== 除去機能テスト ==========
    
    def test_remove_exact_duplicates_keep_first(self, deduplicator, sample_dataset):
        """完全重複除去テスト（最初を保持）"""
        result = deduplicator.remove_exact_duplicates(
            sample_dataset,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        
        assert result.original_count == 5
        assert result.duplicates_found == 1  # 1グループ
        assert result.removed_count == 2  # 2件除去
        assert result.deduplicated_count == 3
        assert result.deduplication_rate == 40.0
        
        # 除去されたIDを確認
        assert set(result.removed_ids) == {"doc2", "doc4"}
    
    def test_remove_exact_duplicates_keep_last(self, deduplicator, sample_dataset):
        """完全重複除去テスト（最後を保持）"""
        result = deduplicator.remove_exact_duplicates(
            sample_dataset,
            strategy=DeduplicationStrategy.KEEP_LAST
        )
        
        assert result.removed_count == 2
        assert result.deduplicated_count == 3
        
        # 最後のIDが残る
        assert "doc4" not in result.removed_ids
    
    def test_remove_exact_duplicates_keep_best(self, deduplicator, sample_dataset):
        """完全重複除去テスト（最高品質を保持）"""
        result = deduplicator.remove_exact_duplicates(
            sample_dataset,
            strategy=DeduplicationStrategy.KEEP_BEST,
            quality_field="quality"
        )
        
        assert result.removed_count == 2
        assert result.deduplicated_count == 3
        
        # 品質0.9のdoc2が残る（最高品質）
        assert "doc2" not in result.removed_ids
    
    def test_remove_exact_duplicates_keep_all(self, deduplicator, sample_dataset):
        """完全重複除去テスト（すべて保持）"""
        result = deduplicator.remove_exact_duplicates(
            sample_dataset,
            strategy=DeduplicationStrategy.KEEP_ALL
        )
        
        assert result.removed_count == 0
        assert result.deduplicated_count == 5  # すべて保持
    
    def test_remove_normalized_duplicates(self, deduplicator):
        """正規化後重複除去テスト"""
        dataset = [
            {"id": "d1", "text": "  HELLO  WORLD  "},
            {"id": "d2", "text": "hello\tworld"},  # 正規化後に重複
            {"id": "d3", "text": "GOODBYE WORLD"},
        ]
        
        result = deduplicator.remove_normalized_duplicates(
            dataset,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        
        assert result.removed_count == 1
        assert result.deduplicated_count == 2
        assert result.removed_ids == ["d2"]
    
    # ========== 結果検証テスト ==========
    
    def test_deduplication_result_fields(self, deduplicator, sample_dataset):
        """DeduplicationResult フィールド検証"""
        result = deduplicator.remove_exact_duplicates(sample_dataset)
        
        # すべてのフィールドが正しく設定される
        assert result.original_count > 0
        assert result.deduplicated_count > 0
        assert result.duplicates_found >= 0
        assert result.removed_count >= 0
        assert 0 <= result.deduplication_rate <= 100
        assert result.processing_time_ms > 0
        assert isinstance(result.duplicate_records, list)
        assert isinstance(result.removed_ids, list)
    
    def test_duplicate_record_information(self, deduplicator, sample_dataset):
        """DuplicateRecord情報検証"""
        result = deduplicator.remove_exact_duplicates(sample_dataset)
        
        if result.duplicate_records:
            record = result.duplicate_records[0]
            
            # 必須フィールド確認
            assert record.primary_id is not None
            assert isinstance(record.duplicate_ids, list)
            assert record.duplicate_type in DuplicateType
            assert 0 <= record.similarity_score <= 1.0
            assert record.first_occurrence is not None
    
    # ========== 統計テスト ==========
    
    def test_duplicate_statistics(self, deduplicator, sample_texts):
        """重複統計情報テスト"""
        deduplicator.detect_exact_duplicates(sample_texts)
        stats = deduplicator.get_duplicate_statistics()
        
        assert "total_duplicate_groups" in stats
        assert "total_duplicate_items" in stats
        assert "avg_group_size" in stats
        assert "max_group_size" in stats
        assert stats["total_duplicate_groups"] == 1
        assert stats["total_duplicate_items"] == 3
    
    # ========== レポート生成テスト ==========
    
    def test_generate_deduplication_report(self, deduplicator, sample_dataset):
        """重複排除レポート生成テスト"""
        result = deduplicator.remove_exact_duplicates(sample_dataset)
        report = deduplicator.generate_deduplication_report(result)
        
        # レポートに必須情報が含まれる
        assert "重複排除レポート" in report
        assert f"{result.original_count}" in report
        assert f"{result.deduplicated_count}" in report
        assert f"{result.deduplication_rate:.2f}%" in report
        assert "✅ 完了" in report
    
    # ========== エッジケーステスト ==========
    
    def test_empty_dataset(self, deduplicator):
        """空データセットテスト"""
        result = deduplicator.remove_exact_duplicates([])
        
        assert result.original_count == 0
        assert result.deduplicated_count == 0
        assert result.duplicates_found == 0
    
    def test_no_duplicates(self, deduplicator):
        """重複なしテスト"""
        dataset = [
            {"id": "1", "text": "unique text 1"},
            {"id": "2", "text": "unique text 2"},
            {"id": "3", "text": "unique text 3"},
        ]
        
        result = deduplicator.remove_exact_duplicates(dataset)
        
        assert result.duplicates_found == 0
        assert result.removed_count == 0
        assert result.deduplicated_count == 3
    
    def test_all_duplicates(self, deduplicator):
        """すべて重複テスト"""
        dataset = [
            {"id": "1", "text": "same text"},
            {"id": "2", "text": "same text"},
            {"id": "3", "text": "same text"},
        ]
        
        result = deduplicator.remove_exact_duplicates(
            dataset,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        
        assert result.duplicates_found == 1
        assert result.removed_count == 2
        assert result.deduplicated_count == 1
        assert abs(result.deduplication_rate - 66.67) < 0.1
    
    def test_special_characters(self, deduplicator):
        """特殊文字テスト"""
        texts = [
            ("id1", "Hello! @#$%^&*()"),
            ("id2", "Hello! @#$%^&*()"),  # 完全重複
            ("id3", "Hello @#$%^&*"),
        ]
        
        duplicates = deduplicator.detect_exact_duplicates(texts)
        
        assert len(duplicates) == 1
        group = list(duplicates.values())[0]
        assert len(group) == 2
    
    def test_unicode_characters(self, deduplicator):
        """Unicode文字テスト"""
        texts = [
            ("id1", "日本語のテキスト"),
            ("id2", "日本語のテキスト"),  # 完全重複
            ("id3", "中文文本"),
        ]
        
        duplicates = deduplicator.detect_exact_duplicates(texts)
        
        assert len(duplicates) == 1
        group = list(duplicates.values())[0]
        assert len(group) == 2
    
    # ========== パフォーマンステスト ==========
    
    def test_performance_large_dataset(self, deduplicator):
        """大規模データセットパフォーマンステスト"""
        # 10,000件のデータセット作成
        dataset = []
        for i in range(10000):
            dataset.append({
                "id": f"id_{i}",
                "text": f"Text number {i % 100}"  # 100種類のテキスト（100倍の重複）
            })
        
        result = deduplicator.remove_exact_duplicates(dataset)
        
        # パフォーマンス確認
        # 1M件/分 = 16,666件/秒 = 0.06ms/件
        items_per_ms = result.original_count / result.processing_time_ms
        assert items_per_ms > 100  # 最低100件/ms
        
        # 重複除去が適切に機能
        assert result.removed_count == 9900
        assert result.deduplicated_count == 100
    
    # ========== 統合テスト ==========
    
    def test_multiple_operations_sequence(self, deduplicator):
        """複数操作の連続テスト"""
        dataset1 = [
            {"id": "1", "text": "text a"},
            {"id": "2", "text": "text a"},
        ]
        
        dataset2 = [
            {"id": "3", "text": "text b"},
            {"id": "4", "text": "text b"},
            {"id": "5", "text": "text b"},
        ]
        
        # 1番目のデータセット処理
        result1 = deduplicator.remove_exact_duplicates(
            dataset1,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        assert result1.removed_count == 1
        
        # 2番目のデータセット処理（内部状態がリセットされる）
        result2 = deduplicator.remove_exact_duplicates(
            dataset2,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        assert result2.removed_count == 2


class TestDeduplicationIntegration:
    """統合テスト"""
    
    def test_full_deduplication_pipeline(self):
        """完全な重複排除パイプラインテスト"""
        deduplicator = ExactDeduplicator()
        
        # データセット作成
        dataset = [
            {"id": "1", "text": "First unique text", "quality": 0.8},
            {"id": "2", "text": "First unique text", "quality": 0.9},  # 重複（高品質）
            {"id": "3", "text": "Second unique text", "quality": 0.7},
            {"id": "4", "text": "  SECOND  UNIQUE  TEXT  ", "quality": 0.85},  # 正規化後重複
            {"id": "5", "text": "Third unique text", "quality": 0.6},
            {"id": "6", "text": "First unique text", "quality": 0.75},  # 重複
        ]
        
        # 完全重複を最高品質で除去
        result = deduplicator.remove_exact_duplicates(
            dataset,
            strategy=DeduplicationStrategy.KEEP_BEST,
            quality_field="quality"
        )
        
        # 正規化後重複を処理
        deduplicated_data = [
            item for item in dataset
            if item["id"] not in result.removed_ids
        ]
        
        result2 = deduplicator.remove_normalized_duplicates(
            deduplicated_data,
            strategy=DeduplicationStrategy.KEEP_FIRST
        )
        
        # 最終結果確認
        final_count = result2.deduplicated_count
        assert final_count == 3  # 3種類のテキスト
        
        # 統計情報確認
        stats = deduplicator.get_duplicate_statistics()
        assert stats["total_duplicate_groups"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
