"""
データ重複排除システム - Exact Duplicates Detection & Removal
主要機能:
- 完全一致重複検出 (ハッシュベース)
- 正規化による重複検出
- 高速重複除去（1M件/分以上）
"""

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class DuplicateType(Enum):
    """重複タイプ分類"""
    EXACT_MATCH = "exact_match"           # 完全一致
    NORMALIZED_MATCH = "normalized_match" # 正規化後一致
    PARTIAL_MATCH = "partial_match"       # 部分一致
    SEMANTIC_MATCH = "semantic_match"     # 意味的一致


class DeduplicationStrategy(Enum):
    """重複排除戦略"""
    KEEP_FIRST = "keep_first"             # 最初のものを保持
    KEEP_LAST = "keep_last"               # 最後のものを保持
    KEEP_BEST = "keep_best"               # 品質最高のものを保持
    KEEP_ALL = "keep_all"                 # すべて保持（重複フラグのみ）


@dataclass
class DuplicateRecord:
    """重複レコード情報"""
    primary_id: str                       # プライマリID
    duplicate_ids: List[str] = field(default_factory=list)  # 重複ID
    duplicate_type: DuplicateType = DuplicateType.EXACT_MATCH
    similarity_score: float = 1.0         # 一致度スコア (0-1)
    first_occurrence: str = ""            # 最初の出現
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeduplicationResult:
    """重複排除結果"""
    original_count: int                   # 元のデータ件数
    deduplicated_count: int               # 重複排除後件数
    duplicates_found: int                 # 検出重複件数
    removed_count: int                    # 除去件数
    deduplication_rate: float             # 重複率 (%)
    processing_time_ms: float             # 処理時間 (ミリ秒)
    duplicate_records: List[DuplicateRecord] = field(default_factory=list)
    removed_ids: List[str] = field(default_factory=list)


class ExactDeduplicator:
    """完全一致重複検出・除去エンジン"""
    
    def __init__(self):
        """初期化"""
        self.hash_map: Dict[str, List[str]] = {}  # ハッシュ → ID マッピング
        self.text_map: Dict[str, List[str]] = {}  # テキスト → ID マッピング
        self.duplicate_pairs: List[Tuple[str, str]] = []
        
    def _hash_text(self, text: str) -> str:
        """テキストのハッシュを計算"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """テキストを正規化"""
        # 改行・スペースの正規化
        normalized = ' '.join(text.split())
        # 小文字に統一
        normalized = normalized.lower()
        # 句読点の正規化
        normalized = normalized.replace('　', ' ').replace('\t', ' ')
        return normalized
    
    def detect_exact_duplicates(
        self,
        texts: List[Tuple[str, str]]  # (ID, text) のリスト
    ) -> Dict[str, List[str]]:
        """
        完全一致重複を検出
        
        Args:
            texts: (ID, テキスト) のタプルリスト
        
        Returns:
            {ハッシュ: [ID, ID, ...]} の辞書
        """
        self.hash_map.clear()
        self.duplicate_pairs.clear()
        
        # ハッシュベースの重複検出
        for text_id, text in texts:
            text_hash = self._hash_text(text)
            
            if text_hash not in self.hash_map:
                self.hash_map[text_hash] = []
            
            self.hash_map[text_hash].append(text_id)
        
        # 重複ペアを抽出
        duplicates = {}
        for text_hash, ids in self.hash_map.items():
            if len(ids) > 1:
                duplicates[text_hash] = ids
                # ペア記録
                for i in range(1, len(ids)):
                    self.duplicate_pairs.append((ids[0], ids[i]))
        
        logger.info(f"Detected {len(duplicates)} duplicate groups")
        return duplicates
    
    def detect_normalized_duplicates(
        self,
        texts: List[Tuple[str, str]]  # (ID, text) のリスト
    ) -> Dict[str, List[str]]:
        """
        正規化後の重複を検出
        
        Args:
            texts: (ID, テキスト) のタプルリスト
        
        Returns:
            {正規化テキスト: [ID, ID, ...]} の辞書
        """
        self.text_map.clear()
        
        # 正規化ベースの重複検出
        for text_id, text in texts:
            normalized = self._normalize_text(text)
            
            if normalized not in self.text_map:
                self.text_map[normalized] = []
            
            self.text_map[normalized].append(text_id)
        
        # 重複をフィルタリング
        duplicates = {
            text: ids for text, ids in self.text_map.items()
            if len(ids) > 1
        }
        
        logger.info(f"Detected {len(duplicates)} normalized duplicate groups")
        return duplicates
    
    def remove_exact_duplicates(
        self,
        dataset: List[Dict[str, Any]],
        text_field: str = "text",
        id_field: str = "id",
        strategy: DeduplicationStrategy = DeduplicationStrategy.KEEP_FIRST,
        quality_field: Optional[str] = None
    ) -> DeduplicationResult:
        """
        完全一致重複を除去
        
        Args:
            dataset: データセット
            text_field: テキストフィールド名
            id_field: IDフィールド名
            strategy: 重複排除戦略
            quality_field: 品質スコアフィールド（KEEP_BESTの場合）
        
        Returns:
            DeduplicationResult
        """
        start_time = datetime.now()
        
        # テキストの抽出
        texts = [
            (str(item.get(id_field, i)), item.get(text_field, ""))
            for i, item in enumerate(dataset)
        ]
        
        # 重複検出
        duplicates = self.detect_exact_duplicates(texts)
        
        # 除去対象IDを決定
        removed_ids: Set[str] = set()
        duplicate_records: List[DuplicateRecord] = []
        
        for text_hash, ids in duplicates.items():
            if len(ids) <= 1:
                continue
            
            # レコード作成
            record = DuplicateRecord(
                primary_id=ids[0],
                duplicate_ids=ids[1:],
                duplicate_type=DuplicateType.EXACT_MATCH,
                similarity_score=1.0,
                first_occurrence=ids[0]
            )
            duplicate_records.append(record)
            
            # 戦略に基づいて除去対象を決定
            if strategy == DeduplicationStrategy.KEEP_FIRST:
                removed_ids.update(ids[1:])
            
            elif strategy == DeduplicationStrategy.KEEP_LAST:
                removed_ids.update(ids[:-1])
            
            elif strategy == DeduplicationStrategy.KEEP_BEST and quality_field:
                # 品質スコアが最高のものを保持
                best_idx = 0
                best_quality = -1
                
                for idx, item_id in enumerate(ids):
                    # IDに対応するアイテムを検索
                    for item in dataset:
                        if str(item.get(id_field)) == item_id:
                            quality = float(item.get(quality_field, 0))
                            if quality > best_quality:
                                best_quality = quality
                                best_idx = idx
                            break
                
                # 最高品質以外を除去
                for i, item_id in enumerate(ids):
                    if i != best_idx:
                        removed_ids.add(item_id)
            
            elif strategy == DeduplicationStrategy.KEEP_ALL:
                # 除去しない（フラグのみ）
                pass
        
        # 重複排除後のデータセット作成
        deduplicated_dataset = [
            item for item in dataset
            if str(item.get(id_field)) not in removed_ids
        ]
        
        # 結果計算
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = DeduplicationResult(
            original_count=len(dataset),
            deduplicated_count=len(deduplicated_dataset),
            duplicates_found=len(duplicates),
            removed_count=len(removed_ids),
            deduplication_rate=(len(removed_ids) / len(dataset) * 100) if dataset else 0.0,
            processing_time_ms=processing_time,
            duplicate_records=duplicate_records,
            removed_ids=list(removed_ids)
        )
        
        logger.info(
            f"Removed {result.removed_count} duplicates "
            f"({result.deduplication_rate:.2f}%) in {processing_time:.1f}ms"
        )
        
        return result
    
    def remove_normalized_duplicates(
        self,
        dataset: List[Dict[str, Any]],
        text_field: str = "text",
        id_field: str = "id",
        strategy: DeduplicationStrategy = DeduplicationStrategy.KEEP_FIRST
    ) -> DeduplicationResult:
        """
        正規化後の重複を除去
        
        Args:
            dataset: データセット
            text_field: テキストフィールド名
            id_field: IDフィールド名
            strategy: 重複排除戦略
        
        Returns:
            DeduplicationResult
        """
        start_time = datetime.now()
        
        # テキストの抽出と正規化
        texts = [
            (str(item.get(id_field, i)), self._normalize_text(item.get(text_field, "")))
            for i, item in enumerate(dataset)
        ]
        
        # 正規化重複検出
        duplicates = self.detect_normalized_duplicates(texts)
        
        # 除去対象IDを決定
        removed_ids: Set[str] = set()
        duplicate_records: List[DuplicateRecord] = []
        
        for normalized_text, ids in duplicates.items():
            if len(ids) <= 1:
                continue
            
            record = DuplicateRecord(
                primary_id=ids[0],
                duplicate_ids=ids[1:],
                duplicate_type=DuplicateType.NORMALIZED_MATCH,
                similarity_score=0.95,
                first_occurrence=ids[0],
                metadata={"normalized_text": normalized_text}
            )
            duplicate_records.append(record)
            
            if strategy == DeduplicationStrategy.KEEP_FIRST:
                removed_ids.update(ids[1:])
            elif strategy == DeduplicationStrategy.KEEP_LAST:
                removed_ids.update(ids[:-1])
        
        # 重複排除後のデータセット作成
        deduplicated_dataset = [
            item for item in dataset
            if str(item.get(id_field)) not in removed_ids
        ]
        
        # 結果計算
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = DeduplicationResult(
            original_count=len(dataset),
            deduplicated_count=len(deduplicated_dataset),
            duplicates_found=len(duplicates),
            removed_count=len(removed_ids),
            deduplication_rate=(len(removed_ids) / len(dataset) * 100) if dataset else 0.0,
            processing_time_ms=processing_time,
            duplicate_records=duplicate_records,
            removed_ids=list(removed_ids)
        )
        
        logger.info(
            f"Removed {result.removed_count} normalized duplicates "
            f"({result.deduplication_rate:.2f}%) in {processing_time:.1f}ms"
        )
        
        return result
    
    def get_duplicate_statistics(self) -> Dict[str, Any]:
        """
        重複統計情報を取得
        
        Returns:
            統計情報
        """
        # 重複グループのサイズ分析
        duplicate_group_sizes = [len(ids) for ids in self.hash_map.values() if len(ids) > 1]
        
        return {
            "total_duplicate_groups": len(duplicate_group_sizes),
            "total_duplicate_items": sum(duplicate_group_sizes),
            "avg_group_size": sum(duplicate_group_sizes) / len(duplicate_group_sizes) if duplicate_group_sizes else 0,
            "max_group_size": max(duplicate_group_sizes) if duplicate_group_sizes else 0,
            "group_size_distribution": dict(Counter(duplicate_group_sizes))
        }
    
    def generate_deduplication_report(
        self,
        result: DeduplicationResult
    ) -> str:
        """
        重複排除レポートを生成
        
        Args:
            result: DeduplicationResult
        
        Returns:
            レポート文字列
        """
        report = f"""
═══════════════════════════════════════════
データ重複排除レポート
═══════════════════════════════════════════

【処理概要】
- 元のデータ件数: {result.original_count:,}
- 重複排除後件数: {result.deduplicated_count:,}
- 検出重複グループ: {result.duplicates_found}
- 除去件数: {result.removed_count}
- 重複率: {result.deduplication_rate:.2f}%
- 処理時間: {result.processing_time_ms:.1f}ms

【重複タイプ分布】
"""
        type_dist = Counter(r.duplicate_type.value for r in result.duplicate_records)
        for dup_type, count in type_dist.items():
            report += f"  - {dup_type}: {count}\n"
        
        report += f"""
【処理結果】
- 圧縮率: {(1 - result.deduplicated_count / result.original_count) * 100:.2f}%
- 効率: {result.original_count / result.processing_time_ms:.1f} items/ms
- ステータス: ✅ 完了

【除去されたID（最初の10件）】
"""
        for removed_id in result.removed_ids[:10]:
            report += f"  - {removed_id}\n"
        
        if len(result.removed_ids) > 10:
            report += f"  ... 他 {len(result.removed_ids) - 10} 件\n"
        
        report += "═══════════════════════════════════════════\n"
        return report
