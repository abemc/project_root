"""
セマンティック重複排除システムテスト
"""

import pytest
import numpy as np
from src.data_processing.semantic_deduplicator import (
    SemanticDeduplicator,
    SemanticSimilarityMetric,
    SemanticDuplicateCluster
)


class TestSemanticSimilarityMetric:
    """セマンティック類似度計算テスト"""
    
    def test_cosine_similarity_identical(self):
        """同じベクトルの類似度テスト"""
        vec = np.array([1, 0, 0], dtype=np.float32)
        similarity = SemanticSimilarityMetric.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001
    
    def test_cosine_similarity_orthogonal(self):
        """直交ベクトルの類似度テスト"""
        vec1 = np.array([1, 0, 0], dtype=np.float32)
        vec2 = np.array([0, 1, 0], dtype=np.float32)
        similarity = SemanticSimilarityMetric.cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.001
    
    def test_cosine_similarity_opposite(self):
        """逆向きベクトルの類似度テスト"""
        vec1 = np.array([1, 0, 0], dtype=np.float32)
        vec2 = np.array([-1, 0, 0], dtype=np.float32)
        similarity = SemanticSimilarityMetric.cosine_similarity(vec1, vec2)
        # 実装では負の値は0に丸められる
        assert abs(similarity - 0.0) < 0.001
    
    def test_cosine_similarity_similar(self):
        """類似ベクトルの類似度テスト"""
        vec1 = np.array([1, 0.1, 0.1], dtype=np.float32)
        vec2 = np.array([1, 0.1, 0.1], dtype=np.float32)
        similarity = SemanticSimilarityMetric.cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001
    
    def test_euclidean_distance(self):
        """ユークリッド距離テスト"""
        vec1 = np.array([0, 0, 0], dtype=np.float32)
        vec2 = np.array([3, 4, 0], dtype=np.float32)
        distance = SemanticSimilarityMetric.euclidean_distance(vec1, vec2)
        assert abs(distance - 5.0) < 0.001
    
    def test_manhattan_distance(self):
        """マンハッタン距離テスト"""
        vec1 = np.array([0, 0, 0], dtype=np.float32)
        vec2 = np.array([3, 4, 5], dtype=np.float32)
        distance = SemanticSimilarityMetric.manhattan_distance(vec1, vec2)
        assert abs(distance - 12.0) < 0.001


class TestSemanticDeduplicator:
    """SemanticDeduplicatorテスト"""
    
    @pytest.fixture
    def deduplicator(self):
        return SemanticDeduplicator()
    
    @pytest.fixture
    def sample_texts(self):
        """サンプルテキスト"""
        return [
            ("id1", "The quick brown fox jumps over the lazy dog"),
            ("id2", "The quick brown fox jumps over the lazy dog"),  # ほぼ同じ
            ("id3", "A fast brown fox leaps over a lazy dog"),       # 類似
            ("id4", "The cat sat on the mat"),
            ("id5", "A feline rested on a rug"),                    # 類似
        ]
    
    @pytest.fixture
    def sample_dataset(self):
        """サンプルデータセット"""
        return [
            {"id": "doc1", "text": "Artificial intelligence is transforming the world", "quality": 0.8},
            {"id": "doc2", "text": "AI is changing the world", "quality": 0.9},  # 類似
            {"id": "doc3", "text": "The weather is sunny today", "quality": 0.7},
            {"id": "doc4", "text": "Today is a nice sunny day", "quality": 0.85},  # 類似
            {"id": "doc5", "text": "Machine learning is part of AI", "quality": 0.8},
        ]
    
    # ========== 埋め込みテスト ==========
    
    def test_embed_texts(self, deduplicator, sample_texts):
        """テキスト埋め込みテスト"""
        embeddings = deduplicator.embed_texts(sample_texts)
        
        assert len(embeddings) == len(sample_texts)
        assert all(isinstance(v, np.ndarray) for v in embeddings.values())
        assert all(len(v) == 384 for v in embeddings.values())
    
    def test_embed_texts_deterministic(self, deduplicator):
        """埋め込みの決定性テスト"""
        text = ("id1", "test text")
        
        # 2回実行
        embedding1 = deduplicator.embed_texts([text])[text[0]]
        embedding2 = deduplicator.embed_texts([text])[text[0]]
        
        # 同じベクトルが得られる
        np.testing.assert_array_almost_equal(embedding1, embedding2)
    
    # ========== 重複検出テスト ==========
    
    def test_detect_semantic_duplicates(self, deduplicator, sample_texts):
        """セマンティック重複検出テスト"""
        duplicates = deduplicator.detect_semantic_duplicates(
            sample_texts,
            similarity_threshold=0.90
        )
        
        # 重複が検出される
        assert len(duplicates) > 0
        
        # 類似度情報が含まれる
        for similar_items in duplicates.values():
            assert all(isinstance(item, tuple) for item in similar_items)
            assert all(0 <= score <= 1 for _, score in similar_items)
    
    def test_detect_semantic_duplicates_threshold(self, deduplicator, sample_texts):
        """閾値による重複検出テスト"""
        # 高い閾値
        duplicates_high = deduplicator.detect_semantic_duplicates(
            sample_texts,
            similarity_threshold=0.99
        )
        
        # 低い閾値
        duplicates_low = deduplicator.detect_semantic_duplicates(
            sample_texts,
            similarity_threshold=0.70
        )
        
        # 閾値が低いほど多くの重複が検出される
        assert len(duplicates_low) >= len(duplicates_high)
    
    # ========== クラスタリングテスト ==========
    
    def test_cluster_similar_items(self, deduplicator, sample_texts):
        """アイテムクラスタリングテスト"""
        clusters = deduplicator.cluster_similar_items(
            sample_texts,
            similarity_threshold=0.85
        )
        
        assert len(clusters) > 0
        assert all(isinstance(c, SemanticDuplicateCluster) for c in clusters)
        
        # クラスタ中心が設定されている
        for cluster in clusters:
            assert cluster.center is not None
            assert len(cluster.center) == 384
            assert len(cluster.similarity_scores) == len(cluster.items)
    
    def test_cluster_coverage(self, deduplicator, sample_texts):
        """クラスタ化の網羅性テスト"""
        clusters = deduplicator.cluster_similar_items(sample_texts)
        
        # すべてのアイテムがクラスタに割り当てられている
        clustered_items = []
        for cluster in clusters:
            clustered_items.extend([item_id for item_id, _ in cluster.items])
        
        original_ids = [item[0] for item in sample_texts]
        assert set(clustered_items) == set(original_ids)
    
    def test_cluster_similarity_scores(self, deduplicator, sample_texts):
        """クラスタ内の類似度スコアテスト"""
        clusters = deduplicator.cluster_similar_items(sample_texts)
        
        for cluster in clusters:
            # 各アイテムの類似度スコアが0-1の範囲
            for item_id, score in cluster.similarity_scores.items():
                assert 0 <= score <= 1
    
    # ========== マージテスト ==========
    
    def test_merge_similar_clusters(self, deduplicator, sample_texts):
        """クラスタマージテスト"""
        # クラスタリング
        clusters_before = deduplicator.cluster_similar_items(
            sample_texts,
            similarity_threshold=0.75
        )
        count_before = len(clusters_before)
        
        # マージ
        clusters_after = deduplicator.merge_similar_clusters(
            similarity_threshold=0.85
        )
        count_after = len(clusters_after)
        
        # マージによってクラスタ数が減少（またはそのまま）
        assert count_after <= count_before
    
    # ========== 除去テスト ==========
    
    def test_remove_semantic_duplicates_keep_first(self, deduplicator, sample_dataset):
        """セマンティック重複除去テスト（最初を保持）"""
        result = deduplicator.remove_semantic_duplicates(
            sample_dataset,
            similarity_threshold=0.85,
            strategy="keep_first"
        )
        
        assert result['original_count'] == 5
        assert result['deduplicated_count'] > 0
        assert result['removed_count'] >= 0
        assert result['removed_count'] + result['deduplicated_count'] == result['original_count']
    
    def test_remove_semantic_duplicates_keep_best(self, deduplicator, sample_dataset):
        """セマンティック重複除去テスト（最高品質を保持）"""
        result = deduplicator.remove_semantic_duplicates(
            sample_dataset,
            similarity_threshold=0.85,
            strategy="keep_best",
            quality_field="quality"
        )
        
        # doc2（品質0.9）が保持される可能性が高い
        assert "doc2" not in result['removed_ids'] or "doc1" in result['removed_ids']
    
    def test_remove_semantic_duplicates_metrics(self, deduplicator, sample_dataset):
        """重複除去メトリクステスト"""
        result = deduplicator.remove_semantic_duplicates(sample_dataset)
        
        # 必須フィールド確認
        assert 'original_count' in result
        assert 'deduplicated_count' in result
        assert 'clusters_found' in result
        assert 'removed_count' in result
        assert 'deduplication_rate' in result
        assert 'processing_time_ms' in result
        assert 'removed_ids' in result
        assert 'kept_ids' in result
        
        # 値の妥当性確認
        assert result['original_count'] > 0
        assert result['deduplicated_count'] > 0
        assert 0 <= result['deduplication_rate'] <= 100
        assert result['processing_time_ms'] > 0
    
    # ========== 統計テスト ==========
    
    def test_similarity_matrix(self, deduplicator, sample_texts):
        """類似度行列テスト"""
        deduplicator.embed_texts(sample_texts)
        matrix = deduplicator.get_semantic_similarity_matrix()
        
        # 行列のサイズ
        assert matrix.shape == (len(sample_texts), len(sample_texts))
        
        # 対角成分はすべて1.0
        for i in range(len(sample_texts)):
            assert abs(matrix[i, i] - 1.0) < 0.001
        
        # 対称行列
        for i in range(len(sample_texts)):
            for j in range(i + 1, len(sample_texts)):
                assert abs(matrix[i, j] - matrix[j, i]) < 0.001
    
    # ========== レポート生成テスト ==========
    
    def test_generate_report(self, deduplicator, sample_dataset):
        """レポート生成テスト"""
        result = deduplicator.remove_semantic_duplicates(sample_dataset)
        report = deduplicator.generate_semantic_deduplication_report(result)
        
        # 必須情報を含む
        assert "セマンティック重複排除レポート" in report
        assert f"{result['original_count']}" in report
        assert f"{result['deduplicated_count']}" in report
        assert "✅ 完了" in report
    
    # ========== エッジケーステスト ==========
    
    def test_empty_dataset(self, deduplicator):
        """空データセットテスト"""
        result = deduplicator.remove_semantic_duplicates([])
        
        assert result['original_count'] == 0
        assert result['deduplicated_count'] == 0
    
    def test_single_item(self, deduplicator):
        """単一アイテムテスト"""
        dataset = [{"id": "1", "text": "single item"}]
        result = deduplicator.remove_semantic_duplicates(dataset)
        
        assert result['original_count'] == 1
        assert result['deduplicated_count'] == 1
        assert result['removed_count'] == 0
    
    def test_no_duplicates(self, deduplicator):
        """重複なしテスト"""
        dataset = [
            {"id": "1", "text": "apple fruit"},
            {"id": "2", "text": "python programming"},
            {"id": "3", "text": "ocean water"},
        ]
        
        result = deduplicator.remove_semantic_duplicates(
            dataset,
            similarity_threshold=0.99
        )
        
        # 高い閾値では重複なし
        assert result['deduplicated_count'] == 3
    
    # ========== パフォーマンステスト ==========
    
    def test_performance_large_dataset(self, deduplicator):
        """大規模データセットパフォーマンステスト"""
        # 100件のデータセット作成
        dataset = []
        for i in range(100):
            dataset.append({
                "id": f"id_{i}",
                "text": f"This is text number {i % 20}"  # 20種類のテキスト
            })
        
        result = deduplicator.remove_semantic_duplicates(dataset)
        
        # パフォーマンス確認
        items_per_ms = result['original_count'] / result['processing_time_ms']
        assert items_per_ms > 10  # 最低10件/ms
    
    # ========== 統合テスト ==========
    
    def test_combined_exact_and_semantic(self, deduplicator):
        """完全+セマンティック重複検出テスト"""
        dataset = [
            {"id": "1", "text": "Hello world"},
            {"id": "2", "text": "Hello world"},  # 完全重複
            {"id": "3", "text": "Hi world"},      # セマンティック重複
            {"id": "4", "text": "Goodbye world"},
        ]
        
        result = deduplicator.remove_semantic_duplicates(
            dataset,
            similarity_threshold=0.90
        )
        
        # 複数の重複が検出される
        assert result['removed_count'] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
