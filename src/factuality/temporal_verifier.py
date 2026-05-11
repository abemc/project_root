"""
時系列検証・事実性確認モジュール

時間軸での知識の一貫性を確認し、ファクト・データの
鮮度度や時系列的矛盾を検出します。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class FreshnessLevel(Enum):
    """ファクト鮮度度レベル"""
    VERY_RECENT = "very_recent"        # 24時間以内
    RECENT = "recent"                  # 1週間以内
    CURRENT = "current"                # 1ヶ月以内
    AGED = "aged"                      # 3ヶ月以内
    OUTDATED = "outdated"              # 3ヶ月以上
    UNKNOWN = "unknown"                # 不明


class TemporalConsistency(Enum):
    """時系列一貫性"""
    FULLY_CONSISTENT = "fully_consistent"        # 完全一貫
    MOSTLY_CONSISTENT = "mostly_consistent"      # ほぼ一貫
    PARTIALLY_CONSISTENT = "partially_consistent"  # 部分的一貫
    INCONSISTENT = "inconsistent"                # 不一貫
    UNKNOWN = "unknown"                          # 判定不可


@dataclass
class FactWithTimestamp:
    """タイムスタンプ付きファクト"""
    fact_id: str
    claim: str
    assertion_date: datetime  # ファクトが主張された日時
    validity_period: Optional[timedelta] = None  # 有効期間（例：365日間）
    source: str = ""          # 情報源
    confidence: float = 0.0   # 信頼度
    
    def is_still_valid(self, current_date: datetime) -> bool:
        """現在日時でまだ有効か確認"""
        if self.validity_period is None:
            return True  # 無期限有効と仮定
        
        expiry_date = self.assertion_date + self.validity_period
        return current_date <= expiry_date
    
    def get_age_days(self, current_date: datetime) -> int:
        """ファクトの経過日数"""
        return (current_date - self.assertion_date).days
    
    def get_freshness_level(self, current_date: datetime) -> FreshnessLevel:
        """ファクト鮮度度を判定"""
        age_days = self.get_age_days(current_date)
        
        if age_days < 1:
            return FreshnessLevel.VERY_RECENT
        elif age_days < 7:
            return FreshnessLevel.RECENT
        elif age_days < 30:
            return FreshnessLevel.CURRENT
        elif age_days < 90:
            return FreshnessLevel.AGED
        else:
            return FreshnessLevel.OUTDATED


@dataclass
class TemporalFactRecord:
    """時系列ファクト記録"""
    fact_id: str
    claim: str
    fact_history: List[FactWithTimestamp] = field(default_factory=list)
    latest_assertion: Optional[FactWithTimestamp] = None
    
    def add_fact(self, fact: FactWithTimestamp) -> None:
        """ファクトを追加（履歴保持）"""
        self.fact_history.append(fact)
        self.latest_assertion = fact
    
    def get_consistency_score(self) -> float:
        """一貫性スコアを計算 (0-1)"""
        if len(self.fact_history) <= 1:
            return 1.0  # 単一のファクトは完全一貫
        
        # 連続したファクト間の矛盾を検出
        inconsistencies = 0
        for i in range(len(self.fact_history) - 1):
            current = self.fact_history[i]
            next_fact = self.fact_history[i + 1]
            
            # 簡単な矛盾検出：クレームが大きく異なる場合
            if self._claims_conflict(current.claim, next_fact.claim):
                inconsistencies += 1
        
        if len(self.fact_history) - 1 == 0:
            return 1.0
        
        consistency = 1.0 - (inconsistencies / (len(self.fact_history) - 1))
        return max(0.0, min(1.0, consistency))
    
    def _claims_conflict(self, claim1: str, claim2: str) -> bool:
        """2つのクレームが矛盾しているかチェック（簡易版）"""
        # 簡潔な実装：完全に異なる場合のみ矛盾と判定
        # 実際の実装ではNLPを使用して意味的矛盾を検出
        return claim1.lower() != claim2.lower()
    
    def get_temporal_consistency(self) -> TemporalConsistency:
        """時系列一貫性を判定"""
        score = self.get_consistency_score()
        
        if score >= 0.95:
            return TemporalConsistency.FULLY_CONSISTENT
        elif score >= 0.75:
            return TemporalConsistency.MOSTLY_CONSISTENT
        elif score >= 0.50:
            return TemporalConsistency.PARTIALLY_CONSISTENT
        else:
            return TemporalConsistency.INCONSISTENT


class TemporalVerifier:
    """時系列検証エンジン"""
    
    def __init__(self):
        """初期化"""
        self.fact_database: Dict[str, TemporalFactRecord] = {}
        self.verification_log: List[Dict] = []
    
    def register_fact(
        self,
        fact_id: str,
        claim: str,
        assertion_date: datetime,
        validity_period: Optional[timedelta] = None,
        source: str = "",
        confidence: float = 0.0,
    ) -> FactWithTimestamp:
        """ファクトを登録"""
        fact = FactWithTimestamp(
            fact_id=fact_id,
            claim=claim,
            assertion_date=assertion_date,
            validity_period=validity_period,
            source=source,
            confidence=confidence,
        )
        
        if fact_id not in self.fact_database:
            self.fact_database[fact_id] = TemporalFactRecord(
                fact_id=fact_id,
                claim=claim,
            )
        
        self.fact_database[fact_id].add_fact(fact)
        return fact
    
    def verify_fact_validity(
        self, fact_id: str, current_date: datetime
    ) -> Tuple[bool, float]:
        """ファクトの有効性を検証"""
        if fact_id not in self.fact_database:
            return False, 0.0  # ファクトが未登録
        
        record = self.fact_database[fact_id]
        
        if record.latest_assertion is None:
            return False, 0.0
        
        # 有効期間チェック
        is_valid = record.latest_assertion.is_still_valid(current_date)
        
        # 鮮度度ペナルティを適用
        freshness = record.latest_assertion.get_freshness_level(current_date)
        freshness_score = self._freshness_to_score(freshness)
        
        # 一貫性をスコアに反映
        consistency_score = record.get_consistency_score()
        
        # 最終スコア計算（信頼度+鮮度度+一貫性の加重平均）
        final_score = (
            record.latest_assertion.confidence * 0.5 +
            freshness_score * 0.3 +
            consistency_score * 0.2
        )
        
        return is_valid, final_score
    
    def _freshness_to_score(self, freshness: FreshnessLevel) -> float:
        """鮮度度をスコアに変換"""
        scores = {
            FreshnessLevel.VERY_RECENT: 1.0,
            FreshnessLevel.RECENT: 0.9,
            FreshnessLevel.CURRENT: 0.75,
            FreshnessLevel.AGED: 0.5,
            FreshnessLevel.OUTDATED: 0.2,
            FreshnessLevel.UNKNOWN: 0.5,
        }
        return scores.get(freshness, 0.5)
    
    def detect_temporal_conflicts(
        self, fact_ids: List[str]
    ) -> List[Tuple[str, str, str]]:
        """複数ファクト間の時系列矛盾を検出"""
        conflicts = []
        
        for i, fact_id1 in enumerate(fact_ids):
            for fact_id2 in fact_ids[i + 1:]:
                if fact_id1 in self.fact_database and fact_id2 in self.fact_database:
                    record1 = self.fact_database[fact_id1]
                    record2 = self.fact_database[fact_id2]
                    
                    # 矛盾を検出
                    if self._records_conflict(record1, record2):
                        conflicts.append((
                            fact_id1,
                            record1.latest_assertion.claim if record1.latest_assertion else "",
                            fact_id2,
                        ))
        
        return conflicts
    
    def _records_conflict(
        self, record1: TemporalFactRecord, record2: TemporalFactRecord
    ) -> bool:
        """2つのファクト記録が矛盾しているか"""
        if record1.latest_assertion is None or record2.latest_assertion is None:
            return False
        
        return record1._claims_conflict(
            record1.latest_assertion.claim,
            record2.latest_assertion.claim,
        )
    
    def get_fact_timeline(self, fact_id: str) -> List[Dict]:
        """ファクトのタイムラインを取得"""
        if fact_id not in self.fact_database:
            return []
        
        record = self.fact_database[fact_id]
        timeline = []
        
        for fact in record.fact_history:
            timeline.append({
                "date": fact.assertion_date.isoformat(),
                "claim": fact.claim,
                "source": fact.source,
                "confidence": fact.confidence,
                "age_days": fact.get_age_days(datetime.now()),
                "freshness": fact.get_freshness_level(datetime.now()).value,
            })
        
        return timeline
    
    def get_verification_report(
        self, fact_id: str, current_date: datetime
    ) -> Dict:
        """ファクト検証レポートを生成"""
        if fact_id not in self.fact_database:
            return {
                "fact_id": fact_id,
                "status": "NOT_FOUND",
                "error": "ファクトが登録されていません",
            }
        
        record = self.fact_database[fact_id]
        is_valid, score = self.verify_fact_validity(fact_id, current_date)
        
        return {
            "fact_id": fact_id,
            "latest_claim": record.latest_assertion.claim if record.latest_assertion else "",
            "is_valid": is_valid,
            "validity_score": score,
            "freshness": record.latest_assertion.get_freshness_level(current_date).value if record.latest_assertion else "UNKNOWN",
            "consistency": record.get_temporal_consistency().value,
            "consistency_score": record.get_consistency_score(),
            "history_size": len(record.fact_history),
            "update_count": len(record.fact_history),
            "latest_update": record.latest_assertion.assertion_date.isoformat() if record.latest_assertion else None,
        }
    
    def get_database_health(self, current_date: datetime) -> Dict:
        """データベースの健全性レポート"""
        if not self.fact_database:
            return {
                "total_facts": 0,
                "valid_facts": 0,
                "outdated_facts": 0,
                "average_score": 0.0,
            }
        
        valid_count = 0
        outdated_count = 0
        total_score = 0.0
        
        for fact_id, record in self.fact_database.items():
            is_valid, score = self.verify_fact_validity(fact_id, current_date)
            
            if is_valid:
                valid_count += 1
            else:
                outdated_count += 1
            
            total_score += score
        
        avg_score = total_score / len(self.fact_database)
        
        return {
            "total_facts": len(self.fact_database),
            "valid_facts": valid_count,
            "outdated_facts": outdated_count,
            "average_score": avg_score,
            "valid_percentage": (valid_count / len(self.fact_database)) * 100,
        }
    
    def update_fact(
        self,
        fact_id: str,
        new_claim: str,
        current_date: datetime,
        source: str = "",
        confidence: float = 0.0,
    ) -> FactWithTimestamp:
        """ファクトを更新"""
        return self.register_fact(
            fact_id=fact_id,
            claim=new_claim,
            assertion_date=current_date,
            source=source,
            confidence=confidence,
        )
    
    def export_database(self) -> Dict:
        """データベースをエクスポート"""
        export_data = {}
        
        for fact_id, record in self.fact_database.items():
            export_data[fact_id] = {
                "latest_claim": record.latest_assertion.claim if record.latest_assertion else "",
                "consistency": record.get_temporal_consistency().value,
                "history": self.get_fact_timeline(fact_id),
            }
        
        return export_data
    
    def reset_database(self):
        """データベースをリセット"""
        self.fact_database = {}
        self.verification_log = []
