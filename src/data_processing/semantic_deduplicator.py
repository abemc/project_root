"""
データ重複排除システム - Semantic Duplicates Detection & Removal
主要機能:
- 埋め込みベースの意味的重複検出
- クラスタリングによる類似度グループ化
- 高速セマンティック類似度計算
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class SemanticSimilarityMetric:
    """セマンティック類似度計算"""
    
    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        コサイン類似度を計算
        
        Args:
            vec1, vec2: ベクトル
        
        Returns:
            類似度 (0-1)
        """
        if len(vec1) == 0 or len(vec2) == 0:
            return 0.0
        
        # ノルム計算
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # コサイン類似度
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        return float(max(0.0, min(1.0, similarity)))
    
    @staticmethod
    def euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        ユークリッド距離を計算
        
        Args:
            vec1, vec2: ベクトル
        
        Returns:
            距離
        """
        return float(np.linalg.norm(vec1 - vec2))
    
    @staticmethod
    def manhattan_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        マンハッタン距離を計算
        
        Args:
            vec1, vec2: ベクトル
        
        Returns:
            距離
        """
        return float(np.sum(np.abs(vec1 - vec2)))


@dataclass
class SemanticDuplicateCluster:
    """セマンティック重複クラスタ"""
    cluster_id: int
    items: List[Tuple[str, np.ndarray]] = field(default_factory=list)  # (ID, ベクトル)
    center: Optional[np.ndarray] = None  # クラスタ中心
    similarity_scores: Dict[str, float] = field(default_factory=dict)  # ID → 中心との類似度


class SemanticDeduplicator:
    """セマンティック重複検出・除去エンジン"""
    
    def __init__(self):
        """初期化"""
        self.embeddings: Dict[str, np.ndarray] = {}
        self.clusters: List[SemanticDuplicateCluster] = []
        self.similarity_metric = SemanticSimilarityMetric()
    
    def _create_mock_embedding(self, text: str, dim: int = 384) -> np.ndarray:
        """
        テキストのモック埋め込みを作成
        実装時は実際の埋め込みモデル（SentenceTransformer等）を使用
        
        Args:
            text: 入力テキスト
            dim: 埋め込み次元
        
        Returns:
            埋め込みベクトル
        """
        # ハッシュベースの高速決定論的ベクトル生成（rng再初期化を避ける）
        import hashlib

        b = hashlib.sha256(text.encode('utf-8')).digest()
        # 短いダイジェストを繰り返して必要長を満たす
        repeat = (dim + len(b) - 1) // len(b)
        data = (b * repeat)[:dim]
        arr = np.frombuffer(data, dtype=np.uint8).astype(np.float32)
        # 0-255 -> -1.0 .. 1.0 の範囲にスケーリング
        vec = (arr / 127.5) - 1.0
        return vec.astype(np.float32)
    
    def embed_texts(
        self,
        texts: List[Tuple[str, str]]  # (ID, text)
    ) -> Dict[str, np.ndarray]:
        """
        テキストを埋め込みベクトルに変換
        
        Args:
            texts: (ID, テキスト) のタプルリスト
        
        Returns:
            {ID: ベクトル} の辞書
        """
        self.embeddings.clear()
        
        for text_id, text in texts:
            # 実装時は以下のように置き換え:
            # embedding = self.embedding_model.encode(text)
            embedding = self._create_mock_embedding(text)
            self.embeddings[text_id] = embedding
        
        logger.info(f"Embedded {len(self.embeddings)} texts")
        return self.embeddings
    
    def detect_semantic_duplicates(
        self,
        texts: List[Tuple[str, str]],  # (ID, text)
        similarity_threshold: float = 0.95
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        セマンティック重複を検出
        
        Args:
            texts: (ID, テキスト) のタプルリスト
            similarity_threshold: 類似度閾値
        
        Returns:
            {ID: [(類似ID, 類似度), ...]} の辞書
        """
        # 埋め込みを生成
        self.embed_texts(texts)

        duplicates: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

        ids = list(self.embeddings.keys())
        if not ids:
            return {}

        # ベクトル行列を作成してコサイン類似度を高速計算
        mat = np.stack([self.embeddings[i] for i in ids], axis=0)  # (n, d)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        # avoid division by zero
        norms[norms == 0] = 1.0
        mat_norm = mat / norms
        sim_matrix = np.dot(mat_norm, mat_norm.T)

        n = sim_matrix.shape[0]
        for i in range(n):
            for j in range(i + 1, n):
                similarity = float(sim_matrix[i, j])
                # clamp to [0,1] to match legacy behavior and avoid numerical drift
                similarity = max(0.0, min(1.0, similarity))
                if similarity >= similarity_threshold:
                    duplicates[ids[i]].append((ids[j], similarity))
                    duplicates[ids[j]].append((ids[i], similarity))

        logger.info(f"Detected {len(duplicates)} items with semantic duplicates (vectorized)")
        return dict(duplicates)
    
    def cluster_similar_items(
        self,
        texts: List[Tuple[str, str]],
        similarity_threshold: float = 0.90
    ) -> List[SemanticDuplicateCluster]:
        """
        類似度に基づいてアイテムをクラスタリング
        
        Args:
            texts: (ID, テキスト) のタプルリスト
            similarity_threshold: クラスタ形成の類似度閾値
        
        Returns:
            SemanticDuplicateClusterのリスト
        """
        # 埋め込みを生成
        self.embed_texts(texts)

        self.clusters.clear()
        ids = list(self.embeddings.keys())
        if not ids:
            return []

        mat = np.stack([self.embeddings[i] for i in ids], axis=0)  # (n, d)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat_norm = mat / norms

        sim_matrix = np.dot(mat_norm, mat_norm.T)

        assigned = set()
        cluster_id_counter = 0
        n = len(ids)

        for i in range(n):
            if ids[i] in assigned:
                continue

            # find all items similar to ids[i]
            similar_idx = np.where(sim_matrix[i] >= similarity_threshold)[0]
            similar_ids = [ids[k] for k in similar_idx if ids[k] not in assigned]

            # create cluster
            cluster = SemanticDuplicateCluster(cluster_id=cluster_id_counter)
            cluster_id_counter += 1

            vectors = []
            for sid in similar_ids:
                vec = self.embeddings[sid]
                cluster.items.append((sid, vec))
                assigned.add(sid)
                vectors.append(vec)

            if vectors:
                cluster.center = np.mean(vectors, axis=0).astype(np.float32)
                for item_id, item_vec in cluster.items:
                    cluster.similarity_scores[item_id] = self.similarity_metric.cosine_similarity(item_vec, cluster.center)

            self.clusters.append(cluster)

        logger.info(f"Formed {len(self.clusters)} semantic clusters (vectorized)")
        return self.clusters
    
    def detect_outliers_in_cluster(
        self,
        cluster: SemanticDuplicateCluster,
        outlier_threshold: float = 0.80
    ) -> List[str]:
        """
        クラスタ内の外れ値を検出
        
        Args:
            cluster: SemanticDuplicateCluster
            outlier_threshold: 外れ値判定の類似度閾値
        
        Returns:
            外れ値のIDリスト
        """
        outliers = []
        
        for item_id, similarity in cluster.similarity_scores.items():
            if similarity < outlier_threshold:
                outliers.append(item_id)
        
        return outliers
    
    def merge_similar_clusters(
        self,
        similarity_threshold: float = 0.85
    ) -> List[SemanticDuplicateCluster]:
        """
        類似したクラスタをマージ
        
        Args:
            similarity_threshold: クラスタ間の類似度閾値
        
        Returns:
            マージ後のクラスタリスト
        """
        if not self.clusters:
            return []
        
        # クラスタ中心間の類似度を計算
        merged = []
        merged_indices = set()
        
        for i, cluster1 in enumerate(self.clusters):
            if i in merged_indices:
                continue
            
            merged_cluster = SemanticDuplicateCluster(
                cluster_id=cluster1.cluster_id,
                items=list(cluster1.items),
                center=cluster1.center.copy() if cluster1.center is not None else None,
                similarity_scores=dict(cluster1.similarity_scores)
            )
            
            # 他のクラスタとマージ可能か確認
            for j in range(i + 1, len(self.clusters)):
                if j in merged_indices:
                    continue
                
                cluster2 = self.clusters[j]
                
                # クラスタ中心間の類似度
                if cluster1.center is not None and cluster2.center is not None:
                    similarity = self.similarity_metric.cosine_similarity(
                        cluster1.center, cluster2.center
                    )
                    
                    if similarity >= similarity_threshold:
                        # クラスタをマージ
                        merged_cluster.items.extend(cluster2.items)
                        merged_cluster.similarity_scores.update(cluster2.similarity_scores)
                        merged_indices.add(j)
            
            # マージ後のクラスタ中心を再計算
            vectors = [vec for _, vec in merged_cluster.items]
            merged_cluster.center = np.mean(vectors, axis=0).astype(np.float32)
            
            merged.append(merged_cluster)
        
        self.clusters = merged
        logger.info(f"Merged to {len(self.clusters)} clusters")
        return self.clusters
    
    def remove_semantic_duplicates(
        self,
        dataset: List[Dict[str, Any]],
        text_field: str = "text",
        id_field: str = "id",
        similarity_threshold: float = 0.95,
        strategy: str = "keep_first",
        quality_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        セマンティック重複を除去
        
        Args:
            dataset: データセット
            text_field: テキストフィールド名
            id_field: IDフィールド名
            similarity_threshold: 類似度閾値
            strategy: 'keep_first', 'keep_last', 'keep_best'
            quality_field: 品質スコアフィールド（keep_bestの場合）
        
        Returns:
            処理結果
        """
        start_time = datetime.now()
        
        # テキストの抽出
        texts = [
            (str(item.get(id_field, i)), item.get(text_field, ""))
            for i, item in enumerate(dataset)
        ]
        
        # クラスタリング
        clusters = self.cluster_similar_items(texts, similarity_threshold)
        
        # 各クラスタから除去対象を決定
        removed_ids: Set[str] = set()
        kept_ids: Set[str] = set()
        
        for cluster in clusters:
            if len(cluster.items) <= 1:
                # 単独アイテム
                kept_ids.add(cluster.items[0][0])
                continue
            
            if strategy == "keep_first":
                kept_ids.add(cluster.items[0][0])
                for item_id, _ in cluster.items[1:]:
                    removed_ids.add(item_id)
            
            elif strategy == "keep_last":
                kept_ids.add(cluster.items[-1][0])
                for item_id, _ in cluster.items[:-1]:
                    removed_ids.add(item_id)
            
            elif strategy == "keep_best" and quality_field:
                # 品質最高のアイテムを保持
                best_idx = 0
                best_quality = -1
                
                for idx, (item_id, _) in enumerate(cluster.items):
                    # IDに対応するアイテムを検索
                    for item in dataset:
                        if str(item.get(id_field)) == item_id:
                            quality = float(item.get(quality_field, 0))
                            if quality > best_quality:
                                best_quality = quality
                                best_idx = idx
                            break
                
                kept_ids.add(cluster.items[best_idx][0])
                for idx, (item_id, _) in enumerate(cluster.items):
                    if idx != best_idx:
                        removed_ids.add(item_id)
        
        # 重複排除後のデータセット
        deduplicated_dataset = [
            item for item in dataset
            if str(item.get(id_field)) in kept_ids
        ]
        
        # 結果計算
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = {
            "original_count": len(dataset),
            "deduplicated_count": len(deduplicated_dataset),
            "clusters_found": len(clusters),
            "removed_count": len(removed_ids),
            "deduplication_rate": (len(removed_ids) / len(dataset) * 100) if dataset else 0.0,
            "processing_time_ms": processing_time,
            "removed_ids": list(removed_ids),
            "kept_ids": list(kept_ids),
            "cluster_sizes": [len(cluster.items) for cluster in clusters]
        }
        
        logger.info(
            f"Removed {result['removed_count']} semantic duplicates "
            f"({result['deduplication_rate']:.2f}%) in {processing_time:.1f}ms"
        )
        
        return result
    
    def get_semantic_similarity_matrix(self) -> np.ndarray:
        """
        埋め込み間の類似度行列を取得
        
        Returns:
            類似度行列 (N×N)
        """
        if not self.embeddings:
            return np.array([])
        
        ids = list(self.embeddings.keys())
        n = len(ids)
        similarity_matrix = np.zeros((n, n), dtype=np.float32)
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity_matrix[i, j] = 1.0
                else:
                    similarity_matrix[i, j] = self.similarity_metric.cosine_similarity(
                        self.embeddings[ids[i]],
                        self.embeddings[ids[j]]
                    )
        
        return similarity_matrix
    
    def generate_semantic_deduplication_report(
        self,
        result: Dict[str, Any]
    ) -> str:
        """
        セマンティック重複排除レポート生成
        
        Args:
            result: 処理結果
        
        Returns:
            レポート文字列
        """
        report = f"""
═══════════════════════════════════════════
セマンティック重複排除レポート
═══════════════════════════════════════════

【処理概要】
- 元のデータ件数: {result['original_count']:,}
- 重複排除後件数: {result['deduplicated_count']:,}
- 検出クラスタ数: {result['clusters_found']}
- 除去件数: {result['removed_count']}
- 重複率: {result['deduplication_rate']:.2f}%
- 処理時間: {result['processing_time_ms']:.1f}ms

【クラスタサイズ分布】
"""
        from collections import Counter
        size_dist = Counter(result['cluster_sizes'])
        
        for size, count in sorted(size_dist.items()):
            report += f"  - サイズ {size}: {count} クラスタ\n"
        
        report += f"""
【処理結果】
- 圧縮率: {(1 - result['deduplicated_count'] / result['original_count']) * 100:.2f}%
- 効率: {result['original_count'] / result['processing_time_ms']:.1f} items/ms
- ステータス: ✅ 完了

【除去されたID（最初の10件）】
"""
        for removed_id in result['removed_ids'][:10]:
            report += f"  - {removed_id}\n"
        
        if len(result['removed_ids']) > 10:
            report += f"  ... 他 {len(result['removed_ids']) - 10} 件\n"
        
        report += "═══════════════════════════════════════════\n"
        return report
