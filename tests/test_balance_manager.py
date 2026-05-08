"""
バランス管理システムテスト
"""

import pytest
import numpy as np
from src.data_processing.balance_manager import (
    ClassImbalanceAnalyzer,
    OversamplingStrategies,
    UndersamplingStrategies,
    StratifiedSplitter,
    BalanceManager,
    BalanceStrategy,
    ImbalanceLevel
)


class TestClassImbalanceAnalyzer:
    """クラス不均衡分析テスト"""
    
    @pytest.fixture
    def analyzer(self):
        return ClassImbalanceAnalyzer()
    
    @pytest.fixture
    def imbalanced_dataset(self):
        """不均衡データセット"""
        dataset = []
        # クラスA: 90件
        for i in range(90):
            dataset.append({"id": f"a_{i}", "class": "A", "value": 1.0})
        # クラスB: 10件
        for i in range(10):
            dataset.append({"id": f"b_{i}", "class": "B", "value": 2.0})
        return dataset
    
    def test_detect_imbalance(self, analyzer, imbalanced_dataset):
        """不均衡検出テスト"""
        result = analyzer.detect_imbalance(imbalanced_dataset)
        
        assert result.total_samples == 100
        assert result.majority_class == "A"
        assert result.minority_class == "B"
        assert abs(result.imbalance_ratio - 9.0) < 0.1
        assert result.imbalance_level == ImbalanceLevel.MODERATELY_IMBALANCED
    
    def test_imbalance_levels(self, analyzer):
        """不均衡レベル判定テスト"""
        # 均衡データセット
        balanced = [
            {"id": "a", "class": "A"},
            {"id": "b", "class": "B"},
            {"id": "c", "class": "C"},
        ]
        result = analyzer.detect_imbalance(balanced)
        assert result.imbalance_level == ImbalanceLevel.BALANCED
    
    def test_recommendations(self, analyzer, imbalanced_dataset):
        """推奨事項生成テスト"""
        result = analyzer.detect_imbalance(imbalanced_dataset)
        
        assert len(result.recommendations) > 0
        assert any("oversampling" in r.lower() for r in result.recommendations)
    
    def test_balance_metrics(self, analyzer, imbalanced_dataset):
        """バランスメトリクステスト"""
        metrics = analyzer.calculate_balance_metrics(imbalanced_dataset)
        
        assert metrics["num_classes"] == 2
        assert metrics["total_samples"] == 100
        assert 0 <= metrics["gini_impurity"] <= 1
        assert 0 <= metrics["normalized_entropy"] <= 1


class TestOversamplingStrategies:
    """オーバーサンプリング戦略テスト"""
    
    @pytest.fixture
    def imbalanced_dataset(self):
        dataset = []
        for i in range(90):
            dataset.append({"id": f"a_{i}", "class": "A", "feat1": 1.0, "feat2": 2.0})
        for i in range(10):
            dataset.append({"id": f"b_{i}", "class": "B", "feat1": 3.0, "feat2": 4.0})
        return dataset
    
    def test_random_oversampling(self, imbalanced_dataset):
        """ランダムオーバーサンプリングテスト"""
        result = OversamplingStrategies.random_oversampling(
            imbalanced_dataset,
            target_ratio=1.0,
            random_seed=42
        )
        
        assert len(result) > len(imbalanced_dataset)
        # クラスBが増加
        class_b_count = sum(1 for item in result if item["class"] == "B")
        assert class_b_count > 10
    
    def test_smote_oversampling(self, imbalanced_dataset):
        """SMOTEテスト"""
        result = OversamplingStrategies.smote_oversampling(
            imbalanced_dataset,
            feature_fields=["feat1", "feat2"],
            k_neighbors=3,
            target_ratio=1.0
        )
        
        assert len(result) > len(imbalanced_dataset)
        # 合成サンプルが追加されている
        class_b_count = sum(1 for item in result if item["class"] == "B")
        assert class_b_count > 10


class TestUndersamplingStrategies:
    """アンダーサンプリング戦略テスト"""
    
    @pytest.fixture
    def imbalanced_dataset(self):
        dataset = []
        for i in range(90):
            dataset.append({"id": f"a_{i}", "class": "A", "feat1": 1.0})
        for i in range(10):
            dataset.append({"id": f"b_{i}", "class": "B", "feat1": 3.0})
        return dataset
    
    def test_random_undersampling(self, imbalanced_dataset):
        """ランダムアンダーサンプリングテスト"""
        result = UndersamplingStrategies.random_undersampling(
            imbalanced_dataset,
            random_seed=42
        )
        
        assert len(result) < len(imbalanced_dataset)
        # クラスAが減少
        class_a_count = sum(1 for item in result if item["class"] == "A")
        assert class_a_count < 90
    
    def test_tomek_links_removal(self, imbalanced_dataset):
        """Tomek Links テスト"""
        result = UndersamplingStrategies.tomek_links_removal(
            imbalanced_dataset,
            feature_fields=["feat1"]
        )
        
        # 境界サンプルが除去される
        assert len(result) <= len(imbalanced_dataset)


class TestStratifiedSplitter:
    """層化分割テスト"""
    
    @pytest.fixture
    def dataset(self):
        dataset = []
        for i in range(60):
            dataset.append({"id": f"a_{i}", "class": "A"})
        for i in range(40):
            dataset.append({"id": f"b_{i}", "class": "B"})
        return dataset
    
    def test_stratified_split(self, dataset):
        """層化分割テスト"""
        train, test = StratifiedSplitter.apply_stratified_split(
            dataset,
            test_size=0.2,
            random_seed=42
        )
        
        # サイズ確認
        assert len(train) + len(test) == len(dataset)
        assert len(test) / len(dataset) == pytest.approx(0.2, abs=0.05)
        
        # クラス分布の確認
        train_class_a = sum(1 for item in train if item["class"] == "A")
        train_ratio = train_class_a / len(train)
        assert train_ratio == pytest.approx(0.6, abs=0.1)
    
    def test_group_kfold(self, dataset):
        """層化k-foldテスト"""
        folds = StratifiedSplitter.apply_group_kfold(
            dataset,
            n_splits=5,
            random_seed=42
        )
        
        assert len(folds) == 5
        
        # 各foldでクラス分布が保持される
        for train, val in folds:
            assert len(train) + len(val) == len(dataset)
            assert len(val) > 0


class TestBalanceManager:
    """BalanceManagerテスト"""
    
    @pytest.fixture
    def manager(self):
        return BalanceManager()
    
    @pytest.fixture
    def imbalanced_dataset(self):
        dataset = []
        for i in range(90):
            dataset.append({
                "id": f"a_{i}",
                "class": "A",
                "feat1": 1.0 + np.random.randn() * 0.1,
                "feat2": 2.0 + np.random.randn() * 0.1
            })
        for i in range(10):
            dataset.append({
                "id": f"b_{i}",
                "class": "B",
                "feat1": 3.0 + np.random.randn() * 0.1,
                "feat2": 4.0 + np.random.randn() * 0.1
            })
        return dataset
    
    def test_analyze_imbalance(self, manager, imbalanced_dataset):
        """不均衡分析テスト"""
        result = manager.analyze_imbalance(imbalanced_dataset)
        
        assert result.total_samples == 100
        assert result.imbalance_ratio > 1
    
    def test_balance_oversampling(self, manager, imbalanced_dataset):
        """オーバーサンプリング戦略テスト"""
        result = manager.balance_dataset(
            imbalanced_dataset,
            strategy=BalanceStrategy.OVERSAMPLING,
            target_ratio=1.0,
            random_seed=42
        )
        
        assert result.original_count == 100
        assert result.balanced_count > 100
        assert result.added_samples > 0
    
    def test_balance_undersampling(self, manager, imbalanced_dataset):
        """アンダーサンプリング戦略テスト"""
        result = manager.balance_dataset(
            imbalanced_dataset,
            strategy=BalanceStrategy.UNDERSAMPLING,
            target_ratio=1.0
        )
        
        assert result.balanced_count < 100
        assert result.removed_samples > 0
    
    def test_balance_smote(self, manager, imbalanced_dataset):
        """SMOTE戦略テスト"""
        result = manager.balance_dataset(
            imbalanced_dataset,
            strategy=BalanceStrategy.SMOTE,
            feature_fields=["feat1", "feat2"],
            target_ratio=1.0
        )
        
        assert result.balanced_count > 100
    
    def test_balance_hybrid(self, manager, imbalanced_dataset):
        """ハイブリッド戦略テスト"""
        result = manager.balance_dataset(
            imbalanced_dataset,
            strategy=BalanceStrategy.HYBRID,
            feature_fields=["feat1", "feat2"]
        )
        
        assert result.balanced_count >= 0
    
    def test_balance_result_structure(self, manager, imbalanced_dataset):
        """バランス結果構造テスト"""
        result = manager.balance_dataset(
            imbalanced_dataset,
            strategy=BalanceStrategy.OVERSAMPLING
        )
        
        assert result.original_count == 100
        assert result.balanced_count > 0
        assert result.balancing_strategy is not None
        assert result.processing_time_ms > 0
        assert len(result.balanced_dataset) == result.balanced_count
    
    def test_get_balance_report(self, manager):
        """バランスレポートテスト"""
        original_dist = {"A": 90, "B": 10}
        balanced_dist = {"A": 50, "B": 50}
        
        report = manager.get_balance_report(original_dist, balanced_dist)
        
        assert "クラスバランス調整レポート" in report
        assert "90" in report
        assert "50" in report
        assert "✅ 完了" in report


class TestBalancingEdgeCases:
    """エッジケーステスト"""
    
    def test_empty_dataset(self):
        """空データセットテスト"""
        analyzer = ClassImbalanceAnalyzer()
        result = analyzer.detect_imbalance([])
        
        assert result.total_samples == 0
    
    def test_single_class_dataset(self):
        """単一クラステスト"""
        analyzer = ClassImbalanceAnalyzer()
        dataset = [{"id": i, "class": "A"} for i in range(10)]
        result = analyzer.detect_imbalance(dataset)
        
        assert result.imbalance_level == ImbalanceLevel.BALANCED
    
    def test_perfectly_balanced_dataset(self):
        """完全に均衡したデータセットテスト"""
        analyzer = ClassImbalanceAnalyzer()
        dataset = (
            [{"id": i, "class": "A"} for i in range(50)] +
            [{"id": i, "class": "B"} for i in range(50)]
        )
        result = analyzer.detect_imbalance(dataset)
        
        assert result.imbalance_level == ImbalanceLevel.BALANCED


class TestBalancingPerformance:
    """パフォーマンステスト"""
    
    def test_large_dataset_balancing(self):
        """大規模データセットバランス調整テスト"""
        # 10,000件のデータセット
        dataset = []
        for i in range(9000):
            dataset.append({"id": i, "class": "A", "feat": 1.0})
        for i in range(1000):
            dataset.append({"id": 9000 + i, "class": "B", "feat": 2.0})
        
        manager = BalanceManager()
        result = manager.balance_dataset(
            dataset,
            strategy=BalanceStrategy.OVERSAMPLING,
            target_ratio=1.0,
            random_seed=42
        )
        
        # パフォーマンス確認
        assert result.processing_time_ms > 0
        assert result.balanced_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
