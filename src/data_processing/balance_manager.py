"""
統計的バランス管理システム
クラス不均衡の検出・分析・解決
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)


class BalanceStrategy(Enum):
    """バランス調整戦略"""
    OVERSAMPLING = "oversampling"           # オーバーサンプリング
    UNDERSAMPLING = "undersampling"         # アンダーサンプリング
    SMOTE = "smote"                         # SMOTE
    TOMEK_LINKS = "tomek_links"             # Tomek Links
    HYBRID = "hybrid"                       # ハイブリッド


class ImbalanceLevel(Enum):
    """不均衡レベル"""
    BALANCED = "balanced"                   # 均衡（比率 < 1.5:1）
    SLIGHTLY_IMBALANCED = "slightly_imbalanced"  # 軽度（1.5:1 ～ 3:1）
    MODERATELY_IMBALANCED = "moderately_imbalanced"  # 中程度（3:1 ～ 10:1）
    HIGHLY_IMBALANCED = "highly_imbalanced"  # 高度（> 10:1）


@dataclass
class ClassDistribution:
    """クラス分布情報"""
    class_name: str
    count: int
    percentage: float
    imbalance_ratio: float  # マジョリティクラスとの比率


@dataclass
class ImbalanceAnalysisResult:
    """不均衡分析結果"""
    total_samples: int
    class_distributions: List[ClassDistribution]
    imbalance_level: ImbalanceLevel
    majority_class: str
    minority_class: str
    imbalance_ratio: float  # max_count / min_count
    processing_time_ms: float
    recommendations: List[str] = field(default_factory=list)


@dataclass
class BalancingResult:
    """バランス調整結果"""
    original_count: int
    balanced_count: int
    target_distribution: Dict[str, int]
    actual_distribution: Dict[str, int]
    balancing_strategy: str
    processing_time_ms: float
    added_samples: int
    removed_samples: int
    balanced_dataset: List[Dict[str, Any]] = field(default_factory=list)


class ClassImbalanceAnalyzer:
    """クラス不均衡分析エンジン"""
    
    def __init__(self):
        """初期化"""
        self.class_distributions: Dict[str, int] = {}
    
    def detect_imbalance(
        self,
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        sample_id_field: str = "id"
    ) -> ImbalanceAnalysisResult:
        """
        クラス不均衡を検出・分析
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            sample_id_field: サンプルIDフィールド名
        
        Returns:
            ImbalanceAnalysisResult
        """
        start_time = datetime.now()
        
        # クラス分布を計算
        class_counts = Counter(
            str(item.get(class_field, "unknown")) for item in dataset
        )
        
        self.class_distributions = dict(class_counts)
        total_samples = len(dataset)
        
        # 詳細な分布情報
        class_distributions = []
        counts_list = sorted(class_counts.values(), reverse=True)
        
        for class_name, count in sorted(class_counts.items()):
            percentage = (count / total_samples * 100) if total_samples > 0 else 0
            imbalance_ratio = counts_list[0] / count if count > 0 else 1
            
            class_distributions.append(ClassDistribution(
                class_name=class_name,
                count=count,
                percentage=percentage,
                imbalance_ratio=imbalance_ratio
            ))
        
        # 不均衡レベルを判定
        if len(class_counts) <= 1:
            imbalance_ratio = 1.0
        else:
            max_count = max(class_counts.values())
            min_count = min(class_counts.values())
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
        
        if imbalance_ratio < 1.5:
            level = ImbalanceLevel.BALANCED
        elif imbalance_ratio < 3:
            level = ImbalanceLevel.SLIGHTLY_IMBALANCED
        elif imbalance_ratio < 10:
            level = ImbalanceLevel.MODERATELY_IMBALANCED
        else:
            level = ImbalanceLevel.HIGHLY_IMBALANCED
        
        # 推奨事項生成
        recommendations = self._generate_recommendations(level, imbalance_ratio)
        
        # 結果生成
        majority_class = max(class_counts, key=class_counts.get) if class_counts else "unknown"
        minority_class = min(class_counts, key=class_counts.get) if class_counts else "unknown"
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = ImbalanceAnalysisResult(
            total_samples=total_samples,
            class_distributions=class_distributions,
            imbalance_level=level,
            majority_class=majority_class,
            minority_class=minority_class,
            imbalance_ratio=imbalance_ratio,
            processing_time_ms=processing_time,
            recommendations=recommendations
        )
        
        logger.info(
            f"Imbalance detected: ratio={imbalance_ratio:.2f}, "
            f"level={level.value}, samples={total_samples}"
        )
        
        return result
    
    def _generate_recommendations(
        self,
        level: ImbalanceLevel,
        ratio: float
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        if level == ImbalanceLevel.BALANCED:
            recommendations.append("Dataset is well-balanced. No action needed.")
        
        elif level == ImbalanceLevel.SLIGHTLY_IMBALANCED:
            recommendations.append("Use weighted loss functions or class weights in training.")
            recommendations.append("Consider stratified k-fold cross-validation.")
        
        elif level == ImbalanceLevel.MODERATELY_IMBALANCED:
            recommendations.append("Apply oversampling for minority class (SMOTE).")
            recommendations.append("Apply undersampling for majority class.")
            recommendations.append("Use class weights in the model.")
        
        else:  # HIGHLY_IMBALANCED
            recommendations.append("Apply aggressive oversampling (SMOTE with k > 5).")
            recommendations.append("Use balanced random forests or other ensemble methods.")
            recommendations.append("Consider anomaly detection techniques.")
            recommendations.append("Use stratified data splitting to preserve class distribution.")
        
        return recommendations
    
    def calculate_balance_metrics(
        self,
        dataset: List[Dict[str, Any]],
        class_field: str = "class"
    ) -> Dict[str, Any]:
        """
        バランスメトリクスを計算
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
        
        Returns:
            メトリクス辞書
        """
        class_counts = Counter(
            str(item.get(class_field, "unknown")) for item in dataset
        )
        
        counts = list(class_counts.values())
        total = sum(counts)
        
        if not counts:
            return {}
        
        # エントロピー計算
        entropy = 0
        for count in counts:
            if count > 0:
                p = count / total
                entropy -= p * np.log2(p)
        
        max_entropy = np.log2(len(counts)) if len(counts) > 1 else 1
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        # Gini不純性
        gini = 1 - sum((count / total) ** 2 for count in counts)
        
        return {
            "num_classes": len(class_counts),
            "total_samples": total,
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,
            "gini_impurity": gini,
            "min_class_size": min(counts),
            "max_class_size": max(counts),
            "avg_class_size": sum(counts) / len(counts),
            "imbalance_ratio": max(counts) / min(counts) if min(counts) > 0 else float('inf')
        }


class OversamplingStrategies:
    """オーバーサンプリング戦略"""
    
    @staticmethod
    def random_oversampling(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        target_ratio: float = 1.0,
        random_seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        ランダムオーバーサンプリング
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            target_ratio: ターゲット比率（マイノリティクラスのサンプル数/マジョリティクラス）
            random_seed: ランダムシード
        
        Returns:
            オーバーサンプルされたデータセット
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # クラス分布を計算
        class_groups = {}
        for item in dataset:
            class_name = str(item.get(class_field, "unknown"))
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append(item)
        
        # マジョリティクラスのサイズを決定
        majority_size = max(len(items) for items in class_groups.values())
        target_size = int(majority_size * target_ratio)
        
        oversampled = list(dataset)  # オリジナルを保持
        
        # マイノリティクラスをオーバーサンプリング
        for class_name, items in class_groups.items():
            if len(items) < target_size:
                # 不足している分をランダムに複製
                shortage = target_size - len(items)
                duplicates = np.random.choice(
                    len(items), size=shortage, replace=True
                )
                
                for idx in duplicates:
                    # 複製アイテムにUUIDを付与して区別
                    duplicate_item = items[idx].copy()
                    if "id" in duplicate_item:
                        duplicate_item["id"] = f"{duplicate_item['id']}_dup_{np.random.randint(10000)}"
                    oversampled.append(duplicate_item)
        
        logger.info(
            f"Random oversampling: {len(dataset)} → {len(oversampled)} samples"
        )
        
        return oversampled
    
    @staticmethod
    def smote_oversampling(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        feature_fields: Optional[List[str]] = None,
        k_neighbors: int = 5,
        target_ratio: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        SMOTE（Synthetic Minority Over-sampling Technique）
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            feature_fields: 特徴量フィールド（Noneの場合は数値フィールド自動検出）
            k_neighbors: k-NN近傍数
            target_ratio: ターゲット比率
        
        Returns:
            SMOTE適用後のデータセット
        """
        if not feature_fields:
            # 数値フィールドを自動検出
            if dataset:
                feature_fields = [
                    k for k in dataset[0].keys()
                    if k != class_field and isinstance(dataset[0].get(k), (int, float))
                ]
        
        if not feature_fields:
            logger.warning("No numeric features found. Using random oversampling instead.")
            return OversamplingStrategies.random_oversampling(
                dataset, class_field, target_ratio
            )
        
        # クラス分布を計算
        class_groups = {}
        for item in dataset:
            class_name = str(item.get(class_field, "unknown"))
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append(item)
        
        # マジョリティクラスのサイズを決定
        majority_size = max(len(items) for items in class_groups.values())
        target_size = int(majority_size * target_ratio)
        
        synthetic_samples = []
        
        # マイノリティクラスのSMOTE合成
        for class_name, items in class_groups.items():
            if len(items) >= target_size:
                continue
            
            # 不足サンプル数
            shortage = target_size - len(items)
            
            # 特徴量を抽出
            features = np.array([
                [float(item.get(f, 0)) for f in feature_fields]
                for item in items
            ])
            
            # 合成サンプルを生成
            for _ in range(shortage):
                # ランダムなマイノリティサンプルを選択
                idx = np.random.randint(len(items))
                base_sample = items[idx]
                
                # k-NNの近傍を探す
                distances = np.linalg.norm(features - features[idx], axis=1)
                k = min(k_neighbors, len(items) - 1)
                nearest_indices = np.argsort(distances)[1:k+1]
                
                # ランダムな近傍を選択
                neighbor_idx = np.random.choice(nearest_indices)
                neighbor_sample = items[neighbor_idx]
                
                # 合成サンプルを生成
                synthetic = base_sample.copy()
                lambda_val = np.random.random()
                
                for f in feature_fields:
                    if f in synthetic:
                        base_val = float(base_sample.get(f, 0))
                        neighbor_val = float(neighbor_sample.get(f, 0))
                        synthetic[f] = base_val + lambda_val * (neighbor_val - base_val)
                
                # IDを更新
                if "id" in synthetic:
                    synthetic["id"] = f"{synthetic['id']}_smote_{len(synthetic_samples)}"
                
                synthetic_samples.append(synthetic)
        
        oversampled = list(dataset) + synthetic_samples
        
        logger.info(
            f"SMOTE oversampling: {len(dataset)} → {len(oversampled)} samples "
            f"({len(synthetic_samples)} synthetic)"
        )
        
        return oversampled


class UndersamplingStrategies:
    """アンダーサンプリング戦略"""
    
    @staticmethod
    def random_undersampling(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        target_ratio: float = 1.0,
        random_seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        ランダムアンダーサンプリング
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            target_ratio: ターゲット比率（最小クラスサイズ × 比率）
            random_seed: ランダムシード
        
        Returns:
            アンダーサンプルされたデータセット
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # クラス分布を計算
        class_groups = {}
        for item in dataset:
            class_name = str(item.get(class_field, "unknown"))
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append(item)
        
        # ターゲットサイズを決定
        min_size = min(len(items) for items in class_groups.values())
        target_size = int(min_size * target_ratio)
        
        undersampled = []
        
        # マジョリティクラスをアンダーサンプリング
        for class_name, items in class_groups.items():
            if len(items) > target_size:
                indices = np.random.choice(
                    len(items), size=target_size, replace=False
                )
                selected = [items[i] for i in indices]
                undersampled.extend(selected)
            else:
                undersampled.extend(items)
        
        logger.info(
            f"Random undersampling: {len(dataset)} → {len(undersampled)} samples"
        )
        
        return undersampled
    
    @staticmethod
    def tomek_links_removal(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        feature_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tomek Links除去
        クラス境界にある多数派サンプルを除去
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            feature_fields: 特徴量フィールド
        
        Returns:
            Tomek Links適用後のデータセット
        """
        if not feature_fields:
            # 数値フィールドを自動検出
            if dataset:
                feature_fields = [
                    k for k in dataset[0].keys()
                    if k != class_field and isinstance(dataset[0].get(k), (int, float))
                ]
        
        if not feature_fields:
            logger.warning("No numeric features found. Using random undersampling instead.")
            return UndersamplingStrategies.random_undersampling(dataset, class_field)
        
        # 特徴量を抽出
        features = np.array([
            [float(item.get(f, 0)) for f in feature_fields]
            for item in dataset
        ])
        
        classes = [str(item.get(class_field, "unknown")) for item in dataset]
        
        # Tomek Linksを検出
        tomek_pairs = []
        n_samples = len(dataset)
        
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                # 異なるクラスか確認
                if classes[i] == classes[j]:
                    continue
                
                # 距離を計算
                distance = np.linalg.norm(features[i] - features[j])
                
                # i と j が互いの最近傍か確認
                is_tomek = True
                for k in range(n_samples):
                    if k != i and k != j:
                        if (classes[k] == classes[i] and
                            np.linalg.norm(features[i] - features[k]) < distance):
                            is_tomek = False
                            break
                        if (classes[k] == classes[j] and
                            np.linalg.norm(features[j] - features[k]) < distance):
                            is_tomek = False
                            break
                
                if is_tomek:
                    tomek_pairs.append((i, j))
        
        # 多数派サンプルを除去
        majority_class = max(
            Counter(classes).items(), key=lambda x: x[1]
        )[0]
        
        removed_indices = set()
        for i, j in tomek_pairs:
            if classes[i] == majority_class:
                removed_indices.add(i)
            if classes[j] == majority_class:
                removed_indices.add(j)
        
        # 結果データセット
        undersampled = [
            item for idx, item in enumerate(dataset)
            if idx not in removed_indices
        ]
        
        logger.info(
            f"Tomek Links removal: {len(dataset)} → {len(undersampled)} samples "
            f"({len(removed_indices)} removed)"
        )
        
        return undersampled


class StratifiedSplitter:
    """層化分割エンジン"""
    
    @staticmethod
    def apply_stratified_split(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        test_size: float = 0.2,
        random_seed: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        層化分割を実行
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            test_size: テストセット比率
            random_seed: ランダムシード
        
        Returns:
            (訓練セット, テストセット)
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # クラス分布を保持してデータを分割
        class_groups = {}
        for idx, item in enumerate(dataset):
            class_name = str(item.get(class_field, "unknown"))
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append((idx, item))
        
        train_data = []
        test_data = []
        
        # 各クラスで分割
        for class_name, items in class_groups.items():
            split_idx = int(len(items) * (1 - test_size))
            
            # ランダムに混合
            np.random.shuffle(items)
            
            train_data.extend([item for _, item in items[:split_idx]])
            test_data.extend([item for _, item in items[split_idx:]])
        
        logger.info(
            f"Stratified split: {len(train_data)} train, {len(test_data)} test"
        )
        
        return train_data, test_data
    
    @staticmethod
    def apply_group_kfold(
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        n_splits: int = 5,
        random_seed: Optional[int] = None
    ) -> List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """
        層化k-fold分割を実行
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            n_splits: 分割数
            random_seed: ランダムシード
        
        Returns:
            [(訓練セット, 検証セット), ...] のリスト
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # クラス分布
        class_groups = {}
        for idx, item in enumerate(dataset):
            class_name = str(item.get(class_field, "unknown"))
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append(item)
        
        folds = [[] for _ in range(n_splits)]
        
        # 各クラスでround-robin方式で分割
        for class_name, items in class_groups.items():
            np.random.shuffle(items)
            
            for fold_idx, item in enumerate(items):
                target_fold = fold_idx % n_splits
                folds[target_fold].append(item)
        
        results = []
        for val_fold_idx in range(n_splits):
            val_data = folds[val_fold_idx]
            train_data = []
            
            for fold_idx in range(n_splits):
                if fold_idx != val_fold_idx:
                    train_data.extend(folds[fold_idx])
            
            results.append((train_data, val_data))
        
        logger.info(f"Group k-fold: {n_splits} folds created")
        
        return results


class BalanceManager:
    """バランス管理統合エンジン"""
    
    def __init__(self):
        """初期化"""
        self.analyzer = ClassImbalanceAnalyzer()
    
    def analyze_imbalance(
        self,
        dataset: List[Dict[str, Any]],
        class_field: str = "class"
    ) -> ImbalanceAnalysisResult:
        """
        不均衡を分析
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
        
        Returns:
            ImbalanceAnalysisResult
        """
        return self.analyzer.detect_imbalance(dataset, class_field)
    
    def balance_dataset(
        self,
        dataset: List[Dict[str, Any]],
        class_field: str = "class",
        strategy: BalanceStrategy = BalanceStrategy.HYBRID,
        target_ratio: float = 1.0,
        **kwargs
    ) -> BalancingResult:
        """
        データセットをバランス調整
        
        Args:
            dataset: データセット
            class_field: クラスフィールド名
            strategy: 戦略
            target_ratio: ターゲット比率
            **kwargs: 戦略別パラメータ
        
        Returns:
            BalancingResult
        """
        start_time = datetime.now()
        original_count = len(dataset)
        original_dist = Counter(
            str(item.get(class_field, "unknown")) for item in dataset
        )
        
        if strategy == BalanceStrategy.OVERSAMPLING:
            balanced = OversamplingStrategies.random_oversampling(
                dataset, class_field, target_ratio, kwargs.get("random_seed")
            )
        
        elif strategy == BalanceStrategy.UNDERSAMPLING:
            balanced = UndersamplingStrategies.random_undersampling(
                dataset, class_field, target_ratio, kwargs.get("random_seed")
            )
        
        elif strategy == BalanceStrategy.SMOTE:
            balanced = OversamplingStrategies.smote_oversampling(
                dataset, class_field, kwargs.get("feature_fields"),
                kwargs.get("k_neighbors", 5), target_ratio
            )
        
        elif strategy == BalanceStrategy.TOMEK_LINKS:
            balanced = UndersamplingStrategies.tomek_links_removal(
                dataset, class_field, kwargs.get("feature_fields")
            )
        
        elif strategy == BalanceStrategy.HYBRID:
            # SMOTEでオーバーサンプリング
            balanced = OversamplingStrategies.smote_oversampling(
                dataset, class_field, kwargs.get("feature_fields"),
                kwargs.get("k_neighbors", 5), 0.9
            )
            # Tomek Linksでアンダーサンプリング
            balanced = UndersamplingStrategies.tomek_links_removal(
                balanced, class_field, kwargs.get("feature_fields")
            )
        
        else:
            balanced = dataset
        
        # 最終分布
        final_dist = Counter(
            str(item.get(class_field, "unknown")) for item in balanced
        )
        
        # ターゲット分布
        target_dist = {}
        for class_name in original_dist.keys():
            target_dist[class_name] = max(
                original_dist[class_name],
                int(max(original_dist.values()) * target_ratio)
            )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = BalancingResult(
            original_count=original_count,
            balanced_count=len(balanced),
            target_distribution=target_dist,
            actual_distribution=dict(final_dist),
            balancing_strategy=strategy.value,
            processing_time_ms=processing_time,
            added_samples=len(balanced) - original_count if len(balanced) > original_count else 0,
            removed_samples=original_count - len(balanced) if original_count > len(balanced) else 0,
            balanced_dataset=balanced
        )
        
        logger.info(
            f"Dataset balanced: {original_count} → {len(balanced)} samples "
            f"using {strategy.value}"
        )
        
        return result
    
    def get_balance_report(
        self,
        original_dist: Dict[str, int],
        balanced_dist: Dict[str, int]
    ) -> str:
        """
        バランス調整レポートを生成
        
        Args:
            original_dist: 元の分布
            balanced_dist: バランス後の分布
        
        Returns:
            レポート文字列
        """
        report = """
═══════════════════════════════════════════
クラスバランス調整レポート
═══════════════════════════════════════════

【元の分布】
"""
        total_orig = sum(original_dist.values())
        for class_name, count in sorted(original_dist.items()):
            pct = (count / total_orig * 100) if total_orig > 0 else 0
            report += f"  {class_name}: {count} ({pct:.1f}%)\n"
        
        report += """
【バランス後の分布】
"""
        total_bal = sum(balanced_dist.values())
        for class_name, count in sorted(balanced_dist.items()):
            pct = (count / total_bal * 100) if total_bal > 0 else 0
            report += f"  {class_name}: {count} ({pct:.1f}%)\n"
        
        report += f"""
【改善効果】
- 総サンプル数: {total_orig} → {total_bal}
- 増減: {total_bal - total_orig:+d}
- ステータス: ✅ 完了

═══════════════════════════════════════════
"""
        return report
