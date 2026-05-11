"""
ソース信頼性レジストリ

信頼性評価済み情報源の一元管理、スコア永続化、
更新履歴追跡を実現するレジストリシステム
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from src.quality_assurance.source_credibility import (
    SourceMetadata,
    CredibilityAnalysisResult,
    CredibilityLevel
)


@dataclass
class SourceRecord:
    """ソースレコード"""
    source_id: str
    metadata: Dict  # SourceMetadataの辞書表現
    latest_credibility_score: float
    credibility_level: str
    
    analysis_count: int = 0
    first_analysis_date: Optional[str] = None
    last_analysis_date: Optional[str] = None
    
    score_history: List[float] = field(default_factory=list)
    level_history: List[str] = field(default_factory=list)
    
    latest_accuracy_rate: Optional[float] = None
    latest_correction_trend: Optional[str] = None
    
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    
    flagged: bool = False
    flag_reason: Optional[str] = None


@dataclass
class RegistryStatistics:
    """レジストリ統計"""
    total_sources: int
    trusted_sources: int
    credible_sources: int
    uncertain_sources: int
    unreliable_sources: int
    
    average_credibility_score: float
    sources_with_improving_trend: int
    sources_with_declining_trend: int
    
    last_updated: str
    total_records: int


class SourceRegistry:
    """ソース信頼性レジストリ"""
    
    def __init__(self, registry_path: Optional[str] = None):
        """初期化"""
        self.registry_path = Path(registry_path) if registry_path else \
                             Path(__file__).parent.parent / "data" / "source_registry.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.records: Dict[str, SourceRecord] = {}
        self._load_registry()
    
    def _load_registry(self):
        """レジストリをファイルから読み込む"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for source_id, record_dict in data.items():
                        # 辞書からSourceRecordを再構築
                        record = SourceRecord(**record_dict)
                        self.records[source_id] = record
            except (json.JSONDecodeError, IOError):
                self.records = {}
    
    def _save_registry(self):
        """レジストリをファイルに保存"""
        data = {}
        for source_id, record in self.records.items():
            record_dict = asdict(record)
            data[source_id] = record_dict
        
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def register_source(
        self,
        analysis_result: CredibilityAnalysisResult,
        tags: Optional[List[str]] = None,
        notes: str = ""
    ) -> SourceRecord:
        """ソースを登録または更新"""
        source_id = analysis_result.source_id
        
        # 既存レコードを取得または作成
        if source_id in self.records:
            record = self.records[source_id]
        else:
            record = SourceRecord(
                source_id=source_id,
                metadata=self._metadata_to_dict(analysis_result.metadata),
                latest_credibility_score=0.0,
                credibility_level="UNKNOWN"
            )
            record.first_analysis_date = datetime.utcnow().isoformat()
        
        # 最新のスコア情報を更新
        record.latest_credibility_score = analysis_result.final_credibility_score
        record.credibility_level = analysis_result.credibility_level.value
        record.last_analysis_date = datetime.utcnow().isoformat()
        record.analysis_count += 1
        
        # スコア履歴を追加
        record.score_history.append(analysis_result.final_credibility_score)
        record.level_history.append(analysis_result.credibility_level.value)
        
        # 精度情報を更新
        record.latest_accuracy_rate = analysis_result.accuracy_history.accuracy_rate
        record.latest_correction_trend = analysis_result.accuracy_history.correction_trend.value
        
        # タグとノートを追加
        if tags:
            record.tags.extend([t for t in tags if t not in record.tags])
        if notes:
            record.notes = notes
        
        self.records[source_id] = record
        self._save_registry()
        
        return record
    
    def get_source(self, source_id: str) -> Optional[SourceRecord]:
        """ソースレコードを取得"""
        return self.records.get(source_id)
    
    def get_all_sources(self) -> List[SourceRecord]:
        """すべてのソースレコードを取得"""
        return list(self.records.values())
    
    def get_sources_by_level(self, level: CredibilityLevel) -> List[SourceRecord]:
        """信頼性レベル別にソースを取得"""
        return [
            record for record in self.records.values()
            if record.credibility_level == level.value
        ]
    
    def get_sources_by_tag(self, tag: str) -> List[SourceRecord]:
        """タグ別にソースを取得"""
        return [
            record for record in self.records.values()
            if tag in record.tags
        ]
    
    def flag_source(
        self,
        source_id: str,
        reason: Optional[str] = None,
        unflag: bool = False
    ) -> bool:
        """ソースにフラグを設定"""
        if source_id not in self.records:
            return False
        
        record = self.records[source_id]
        if unflag:
            record.flagged = False
            record.flag_reason = None
        else:
            record.flagged = True
            record.flag_reason = reason
        
        self._save_registry()
        return True
    
    def get_flagged_sources(self) -> List[SourceRecord]:
        """フラグが設定されたソースを取得"""
        return [
            record for record in self.records.values()
            if record.flagged
        ]
    
    def get_score_trend(self, source_id: str) -> Optional[List[float]]:
        """スコアトレンドを取得"""
        if source_id not in self.records:
            return None
        
        return self.records[source_id].score_history
    
    def get_average_score(self, source_id: str) -> Optional[float]:
        """平均スコアを計算"""
        trend = self.get_score_trend(source_id)
        if not trend or len(trend) == 0:
            return None
        
        return sum(trend) / len(trend)
    
    def get_score_stability(self, source_id: str) -> Optional[float]:
        """スコアの安定性を計算（標準偏差）"""
        trend = self.get_score_trend(source_id)
        if not trend or len(trend) < 2:
            return None
        
        import statistics
        return statistics.stdev(trend)
    
    def get_statistics(self) -> RegistryStatistics:
        """レジストリ統計を取得"""
        if len(self.records) == 0:
            return RegistryStatistics(
                total_sources=0,
                trusted_sources=0,
                credible_sources=0,
                uncertain_sources=0,
                unreliable_sources=0,
                average_credibility_score=0.0,
                sources_with_improving_trend=0,
                sources_with_declining_trend=0,
                last_updated=datetime.utcnow().isoformat(),
                total_records=0
            )
        
        # レベル別カウント
        level_counts = {
            CredibilityLevel.TRUSTED.value: 0,
            CredibilityLevel.CREDIBLE.value: 0,
            CredibilityLevel.UNCERTAIN.value: 0,
            CredibilityLevel.UNRELIABLE.value: 0
        }
        
        scores = []
        improving_count = 0
        declining_count = 0
        
        for record in self.records.values():
            level_counts[record.credibility_level] = level_counts.get(
                record.credibility_level, 0) + 1
            scores.append(record.latest_credibility_score)
            
            if record.latest_correction_trend == "improving":
                improving_count += 1
            elif record.latest_correction_trend == "declining":
                declining_count += 1
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return RegistryStatistics(
            total_sources=len(self.records),
            trusted_sources=level_counts[CredibilityLevel.TRUSTED.value],
            credible_sources=level_counts[CredibilityLevel.CREDIBLE.value],
            uncertain_sources=level_counts[CredibilityLevel.UNCERTAIN.value],
            unreliable_sources=level_counts[CredibilityLevel.UNRELIABLE.value],
            average_credibility_score=avg_score,
            sources_with_improving_trend=improving_count,
            sources_with_declining_trend=declining_count,
            last_updated=datetime.utcnow().isoformat(),
            total_records=len(self.records)
        )
    
    def get_top_sources(self, n: int = 10) -> List[Tuple[str, float]]:
        """上位のソースを取得"""
        sorted_records = sorted(
            self.records.values(),
            key=lambda r: r.latest_credibility_score,
            reverse=True
        )
        return [(r.source_id, r.latest_credibility_score) for r in sorted_records[:n]]
    
    def get_bottom_sources(self, n: int = 10) -> List[Tuple[str, float]]:
        """下位のソースを取得"""
        sorted_records = sorted(
            self.records.values(),
            key=lambda r: r.latest_credibility_score
        )
        return [(r.source_id, r.latest_credibility_score) for r in sorted_records[:n]]
    
    def export_registry(self, export_path: str) -> bool:
        """レジストリをエクスポート"""
        try:
            data = {}
            for source_id, record in self.records.items():
                record_dict = asdict(record)
                data[source_id] = record_dict
            
            export_path_obj = Path(export_path)
            export_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path_obj, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False
    
    def import_registry(self, import_path: str, merge: bool = False) -> bool:
        """レジストリをインポート"""
        try:
            import_path_obj = Path(import_path)
            
            if not import_path_obj.exists():
                return False
            
            with open(import_path_obj, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not merge:
                self.records = {}
            
            for source_id, record_dict in data.items():
                record = SourceRecord(**record_dict)
                self.records[source_id] = record
            
            self._save_registry()
            return True
        except Exception as e:
            print(f"Import failed: {e}")
            return False
    
    def delete_source(self, source_id: str) -> bool:
        """ソースを削除"""
        if source_id not in self.records:
            return False
        
        del self.records[source_id]
        self._save_registry()
        return True
    
    def clear_registry(self) -> bool:
        """レジストリをクリア"""
        self.records = {}
        self._save_registry()
        return True
    
    def generate_report(self) -> str:
        """レジストリレポートを生成"""
        stats = self.get_statistics()
        
        report = []
        report.append("=" * 60)
        report.append("SOURCE REGISTRY REPORT")
        report.append(f"Generated: {stats.last_updated}")
        report.append("=" * 60)
        report.append("")
        
        # 概要
        report.append("SUMMARY")
        report.append("-" * 60)
        report.append(f"Total Sources: {stats.total_sources}")
        report.append(f"Average Credibility Score: {stats.average_credibility_score:.2f}")
        report.append("")
        
        # レベル分布
        report.append("DISTRIBUTION BY CREDIBILITY LEVEL")
        report.append("-" * 60)
        report.append(f"Trusted: {stats.trusted_sources} ({stats.trusted_sources/max(stats.total_sources,1)*100:.1f}%)")
        report.append(f"Credible: {stats.credible_sources} ({stats.credible_sources/max(stats.total_sources,1)*100:.1f}%)")
        report.append(f"Uncertain: {stats.uncertain_sources} ({stats.uncertain_sources/max(stats.total_sources,1)*100:.1f}%)")
        report.append(f"Unreliable: {stats.unreliable_sources} ({stats.unreliable_sources/max(stats.total_sources,1)*100:.1f}%)")
        report.append("")
        
        # トレンド
        report.append("TRENDS")
        report.append("-" * 60)
        report.append(f"Sources with Improving Trend: {stats.sources_with_improving_trend}")
        report.append(f"Sources with Declining Trend: {stats.sources_with_declining_trend}")
        report.append("")
        
        # トップソース
        report.append("TOP 5 SOURCES")
        report.append("-" * 60)
        for i, (source_id, score) in enumerate(self.get_top_sources(5), 1):
            report.append(f"{i}. {source_id}: {score:.2f}")
        report.append("")
        
        # ボトムソース
        report.append("BOTTOM 5 SOURCES")
        report.append("-" * 60)
        for i, (source_id, score) in enumerate(self.get_bottom_sources(5), 1):
            report.append(f"{i}. {source_id}: {score:.2f}")
        report.append("")
        
        # フラグ付きソース
        flagged = self.get_flagged_sources()
        if flagged:
            report.append("FLAGGED SOURCES")
            report.append("-" * 60)
            for record in flagged:
                report.append(f"- {record.source_id}: {record.flag_reason}")
            report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    @staticmethod
    def _metadata_to_dict(metadata: SourceMetadata) -> Dict:
        """メタデータを辞書に変換"""
        return {
            "source_id": metadata.source_id,
            "domain": metadata.domain,
            "organization": metadata.organization,
            "country": metadata.country,
            "language": metadata.language,
            "website_rank": metadata.website_rank,
            "social_followers": metadata.social_followers
        }
