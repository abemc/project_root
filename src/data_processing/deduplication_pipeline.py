"""
データ重複排除統合パイプライン
完全一致とセマンティック重複を組み合わせた統合処理
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

from src.data_processing.deduplicator import (
    ExactDeduplicator,
    DeduplicationStrategy as ExactStrategy
)
from src.data_processing.semantic_deduplicator import SemanticDeduplicator

logger = logging.getLogger(__name__)


class PipelineMode(Enum):
    """パイプラインモード"""
    EXACT_ONLY = "exact_only"                 # 完全一致のみ
    SEMANTIC_ONLY = "semantic_only"           # セマンティックのみ
    EXACT_THEN_SEMANTIC = "exact_then_semantic"  # 順序処理
    PARALLEL = "parallel"                     # 並列処理（ユニオン）


@dataclass
class PipelineConfig:
    """パイプライン設定"""
    mode: PipelineMode = PipelineMode.EXACT_THEN_SEMANTIC
    text_field: str = "text"
    id_field: str = "id"
    quality_field: Optional[str] = None
    exact_strategy: str = "keep_best"
    semantic_strategy: str = "keep_best"
    exact_keep_all: bool = False
    semantic_threshold: float = 0.95
    enable_normalization: bool = True
    enable_report_generation: bool = True


@dataclass
class PipelineProcessingStep:
    """パイプライン処理ステップ"""
    step_name: str
    duplicates_found: int
    removed_count: int
    removed_ids: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """パイプライン処理結果"""
    original_count: int
    final_count: int
    total_removed: int
    deduplication_rate: float
    total_processing_time_ms: float
    steps: List[PipelineProcessingStep] = field(default_factory=list)
    deduplicated_dataset: List[Dict[str, Any]] = field(default_factory=list)
    all_removed_ids: List[str] = field(default_factory=list)
    config: Optional[PipelineConfig] = None


class DataDeduplicationPipeline:
    """データ重複排除統合パイプライン"""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        初期化
        
        Args:
            config: パイプライン設定
        """
        self.config = config or PipelineConfig()
        self.exact_deduplicator = ExactDeduplicator()
        self.semantic_deduplicator = SemanticDeduplicator()
        self.last_result: Optional[PipelineResult] = None
    
    def process_exact_deduplication(
        self,
        dataset: List[Dict[str, Any]]
    ) -> Tuple[PipelineProcessingStep, List[Dict[str, Any]]]:
        """
        完全一致重複排除を実行
        
        Args:
            dataset: 入力データセット
        
        Returns:
            (処理ステップ, 重複排除後のデータセット)
        """
        start_time = datetime.now()
        
        # ExactDeduplicator用の戦略に変換
        if self.config.exact_strategy == "keep_best":
            strategy = ExactStrategy.KEEP_BEST
        elif self.config.exact_strategy == "keep_last":
            strategy = ExactStrategy.KEEP_LAST
        else:
            strategy = ExactStrategy.KEEP_FIRST
        
        # 完全一致除去
        result1 = self.exact_deduplicator.remove_exact_duplicates(
            dataset,
            text_field=self.config.text_field,
            id_field=self.config.id_field,
            strategy=strategy,
            quality_field=self.config.quality_field
        )
        
        # 正規化による除去（有効な場合）
        result2 = None
        removed_ids = set(result1.removed_ids)
        
        if self.config.enable_normalization:
            deduplicated_data = [
                item for item in dataset
                if str(item.get(self.config.id_field)) not in removed_ids
            ]
            
            result2 = self.exact_deduplicator.remove_normalized_duplicates(
                deduplicated_data,
                text_field=self.config.text_field,
                id_field=self.config.id_field
            )
            
            removed_ids.update(result2.removed_ids)
        
        # 最終的な除去後データセット
        deduplicated_data = [
            item for item in dataset
            if str(item.get(self.config.id_field)) not in removed_ids
        ]
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # ステップ情報
        step = PipelineProcessingStep(
            step_name="Exact Deduplication",
            duplicates_found=result1.duplicates_found + (result2.duplicates_found if result2 else 0),
            removed_count=len(removed_ids),
            removed_ids=list(removed_ids),
            processing_time_ms=processing_time,
            metrics={
                "exact_duplicates": result1.duplicates_found,
                "normalized_duplicates": result2.duplicates_found if result2 else 0,
                "exact_dedup_rate": result1.deduplication_rate,
                "normalized_dedup_rate": result2.deduplication_rate if result2 else 0.0
            }
        )
        
        return step, deduplicated_data
    
    def process_semantic_deduplication(
        self,
        dataset: List[Dict[str, Any]]
    ) -> Tuple[PipelineProcessingStep, List[Dict[str, Any]]]:
        """
        セマンティック重複排除を実行
        
        Args:
            dataset: 入力データセット
        
        Returns:
            (処理ステップ, 重複排除後のデータセット)
        """
        start_time = datetime.now()
        
        result = self.semantic_deduplicator.remove_semantic_duplicates(
            dataset,
            text_field=self.config.text_field,
            id_field=self.config.id_field,
            similarity_threshold=self.config.semantic_threshold,
            strategy=self.config.semantic_strategy,
            quality_field=self.config.quality_field
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # 重複排除後のデータセット
        deduplicated_data = [
            item for item in dataset
            if str(item.get(self.config.id_field)) in result['kept_ids']
        ]
        
        # ステップ情報
        step = PipelineProcessingStep(
            step_name="Semantic Deduplication",
            duplicates_found=result['clusters_found'],
            removed_count=result['removed_count'],
            removed_ids=result['removed_ids'],
            processing_time_ms=processing_time,
            metrics={
                "clusters_formed": result['clusters_found'],
                "avg_cluster_size": sum(result['cluster_sizes']) / len(result['cluster_sizes']) if result['cluster_sizes'] else 0,
                "dedup_rate": result['deduplication_rate']
            }
        )
        
        return step, deduplicated_data
    
    def process_exact_then_semantic(
        self,
        dataset: List[Dict[str, Any]]
    ) -> PipelineResult:
        """
        完全一致 → セマンティックの順序処理
        
        Args:
            dataset: 入力データセット
        
        Returns:
            PipelineResult
        """
        pipeline_start = datetime.now()
        steps = []
        all_removed_ids = []
        
        # Step 1: 完全一致除去
        exact_step, data_after_exact = self.process_exact_deduplication(dataset)
        steps.append(exact_step)
        all_removed_ids.extend(exact_step.removed_ids)
        
        # Step 2: セマンティック除去
        if data_after_exact:  # データが残っている場合
            semantic_step, data_after_semantic = self.process_semantic_deduplication(
                data_after_exact
            )
            steps.append(semantic_step)
            all_removed_ids.extend(semantic_step.removed_ids)
        else:
            # データがない場合はスキップ
            data_after_semantic = []
        
        # 結果生成
        total_processing_time = (
            datetime.now() - pipeline_start
        ).total_seconds() * 1000
        
        result = PipelineResult(
            original_count=len(dataset),
            final_count=len(data_after_semantic),
            total_removed=len(all_removed_ids),
            deduplication_rate=(len(all_removed_ids) / len(dataset) * 100) if dataset else 0.0,
            total_processing_time_ms=total_processing_time,
            steps=steps,
            deduplicated_dataset=data_after_semantic,
            all_removed_ids=all_removed_ids,
            config=self.config
        )
        
        self.last_result = result
        return result
    
    def process_parallel(
        self,
        dataset: List[Dict[str, Any]]
    ) -> PipelineResult:
        """
        並列処理（完全 OR セマンティック）
        
        Args:
            dataset: 入力データセット
        
        Returns:
            PipelineResult
        """
        pipeline_start = datetime.now()
        steps = []
        
        # Step 1: 完全一致除去
        exact_step, data_after_exact = self.process_exact_deduplication(dataset)
        steps.append(exact_step)
        exact_removed = set(exact_step.removed_ids)
        
        # Step 2: セマンティック除去（元のデータセット対象）
        semantic_step, _ = self.process_semantic_deduplication(dataset)
        steps.append(semantic_step)
        semantic_removed = set(semantic_step.removed_ids)
        
        # ユニオン（どちらかで除去されたもの）
        all_removed = exact_removed | semantic_removed
        
        # 最終的な重複排除後データセット
        deduplicated_data = [
            item for item in dataset
            if str(item.get(self.config.id_field)) not in all_removed
        ]
        
        total_processing_time = (
            datetime.now() - pipeline_start
        ).total_seconds() * 1000
        
        result = PipelineResult(
            original_count=len(dataset),
            final_count=len(deduplicated_data),
            total_removed=len(all_removed),
            deduplication_rate=(len(all_removed) / len(dataset) * 100) if dataset else 0.0,
            total_processing_time_ms=total_processing_time,
            steps=steps,
            deduplicated_dataset=deduplicated_data,
            all_removed_ids=list(all_removed),
            config=self.config
        )
        
        self.last_result = result
        return result
    
    def process(
        self,
        dataset: List[Dict[str, Any]]
    ) -> PipelineResult:
        """
        パイプラインを実行
        
        Args:
            dataset: 入力データセット
        
        Returns:
            PipelineResult
        """
        logger.info(
            f"Starting deduplication pipeline (mode: {self.config.mode.value}, "
            f"items: {len(dataset)})"
        )
        
        if self.config.mode == PipelineMode.EXACT_ONLY:
            step, deduplicated_data = self.process_exact_deduplication(dataset)
            result = PipelineResult(
                original_count=len(dataset),
                final_count=len(deduplicated_data),
                total_removed=step.removed_count,
                deduplication_rate=(step.removed_count / len(dataset) * 100) if dataset else 0.0,
                total_processing_time_ms=step.processing_time_ms,
                steps=[step],
                deduplicated_dataset=deduplicated_data,
                all_removed_ids=step.removed_ids,
                config=self.config
            )
        
        elif self.config.mode == PipelineMode.SEMANTIC_ONLY:
            step, deduplicated_data = self.process_semantic_deduplication(dataset)
            result = PipelineResult(
                original_count=len(dataset),
                final_count=len(deduplicated_data),
                total_removed=step.removed_count,
                deduplication_rate=(step.removed_count / len(dataset) * 100) if dataset else 0.0,
                total_processing_time_ms=step.processing_time_ms,
                steps=[step],
                deduplicated_dataset=deduplicated_data,
                all_removed_ids=step.removed_ids,
                config=self.config
            )
        
        elif self.config.mode == PipelineMode.EXACT_THEN_SEMANTIC:
            result = self.process_exact_then_semantic(dataset)
        
        elif self.config.mode == PipelineMode.PARALLEL:
            result = self.process_parallel(dataset)
        
        else:
            raise ValueError(f"Unknown mode: {self.config.mode}")
        
        self.last_result = result
        
        logger.info(
            f"Pipeline completed: {result.total_removed} duplicates removed "
            f"({result.deduplication_rate:.2f}%) in {result.total_processing_time_ms:.1f}ms"
        )
        
        return result
    
    def generate_pipeline_report(
        self,
        result: Optional[PipelineResult] = None
    ) -> str:
        """
        パイプライン処理レポート生成
        
        Args:
            result: PipelineResult（Noneの場合は最後の結果を使用）
        
        Returns:
            レポート文字列
        """
        result = result or self.last_result
        if not result:
            return "No pipeline result available"
        
        report = f"""
═══════════════════════════════════════════════════════════════
データ重複排除パイプライン - 統合処理レポート
═══════════════════════════════════════════════════════════════

【パイプライン設定】
- モード: {result.config.mode.value if result.config else 'Unknown'}
- テキストフィールド: {result.config.text_field if result.config else 'Unknown'}
- IDフィールド: {result.config.id_field if result.config else 'Unknown'}

【処理結果】
- 元のデータ件数: {result.original_count:,}
- 最終データ件数: {result.final_count:,}
- 除去件数: {result.total_removed:,}
- 重複率: {result.deduplication_rate:.2f}%
- 圧縮率: {(1 - result.final_count / result.original_count) * 100:.2f}%
- 総処理時間: {result.total_processing_time_ms:.1f}ms

【処理ステップ詳細】
"""
        for i, step in enumerate(result.steps, 1):
            report += f"""
Step {i}: {step.step_name}
  - 検出重複数: {step.duplicates_found}
  - 除去件数: {step.removed_count}
  - 処理時間: {step.processing_time_ms:.1f}ms
"""
            for metric_name, metric_value in step.metrics.items():
                if isinstance(metric_value, float):
                    report += f"    - {metric_name}: {metric_value:.2f}\n"
                else:
                    report += f"    - {metric_name}: {metric_value}\n"
        
        report += """
【除去されたID（最初の20件）】
"""
        for removed_id in result.all_removed_ids[:20]:
            report += f"  - {removed_id}\n"
        
        if len(result.all_removed_ids) > 20:
            report += f"  ... 他 {len(result.all_removed_ids) - 20} 件\n"
        
        report += """
【処理効率】
"""
        if result.total_processing_time_ms > 0:
            throughput = result.original_count / result.total_processing_time_ms
            report += f"  - スループット: {throughput:.1f} items/ms\n"
        
        report += """
═══════════════════════════════════════════════════════════════
ステータス: ✅ 完了
═══════════════════════════════════════════════════════════════
"""
        return report
