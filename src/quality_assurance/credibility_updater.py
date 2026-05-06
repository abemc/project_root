"""
信頼性スコア更新エンジン

検証結果を基に信頼性スコアを動的に更新し、
トレンド分析と自動アラート生成を実現
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import statistics


class UpdateReason(Enum):
    """更新理由"""
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    CORRECTION_PUBLISHED = "correction_published"
    RETRACTION_ISSUED = "retraction_issued"
    ACCURACY_IMPROVEMENT = "accuracy_improvement"
    ACCURACY_DECLINE = "accuracy_decline"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    PERIODIC_REVIEW = "periodic_review"


class AlertLevel(Enum):
    """アラートレベル"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ScoreUpdate:
    """スコア更新記録"""
    source_id: str
    old_score: float
    new_score: float
    score_change: float
    update_reason: UpdateReason
    
    verification_result: Optional[Dict] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class Alert:
    """アラート"""
    source_id: str
    alert_level: AlertLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    addressed: bool = False
    response: Optional[str] = None


@dataclass
class UpdateStatistics:
    """更新統計"""
    total_updates: int
    average_score_change: float
    max_positive_change: float
    max_negative_change: float
    
    updates_by_reason: Dict[str, int]
    sources_improved: int
    sources_declined: int
    
    active_alerts: int
    total_alerts: int


class CredibilityScoreUpdater:
    """信頼性スコア更新エンジン"""
    
    def __init__(self, sensitivity: float = 0.5):
        """初期化
        
        Args:
            sensitivity: スコア変更の敏感度 (0.0-1.0)
                低い値: 小さな変更のみ
                高い値: 大きな変更を許可
        """
        self.sensitivity = max(0.0, min(sensitivity, 1.0))
        
        self.updates_history: List[ScoreUpdate] = []
        self.alerts: List[Alert] = []
        self.source_scores: Dict[str, float] = {}
    
    def update_score_on_verification(
        self,
        source_id: str,
        current_score: float,
        verification_passed: bool,
        accuracy_rate: float = None,
        confidence: float = 1.0,
        verification_details: Dict = None
    ) -> ScoreUpdate:
        """検証結果に基づくスコア更新"""
        
        if verification_passed:
            update_reason = UpdateReason.VERIFICATION_PASSED
            base_adjustment = 0.05 * self.sensitivity
        else:
            update_reason = UpdateReason.VERIFICATION_FAILED
            base_adjustment = -0.10 * self.sensitivity
        
        # 信頼度に基づいて調整幅を変更
        adjustment = base_adjustment * confidence
        
        # 精度率が提供されている場合は追加調整
        if accuracy_rate is not None:
            if accuracy_rate > 0.9:
                adjustment += 0.03 * self.sensitivity
            elif accuracy_rate < 0.5:
                adjustment -= 0.05 * self.sensitivity
        
        new_score = max(0.0, min(current_score + adjustment, 1.0))
        
        update = ScoreUpdate(
            source_id=source_id,
            old_score=current_score,
            new_score=new_score,
            score_change=new_score - current_score,
            update_reason=update_reason,
            verification_result=verification_details
        )
        
        self.updates_history.append(update)
        self.source_scores[source_id] = new_score
        
        # アラートの生成
        self._check_and_generate_alerts(source_id, update)
        
        return update
    
    def update_score_on_correction(
        self,
        source_id: str,
        current_score: float,
        correction_type: str = "minor"  # minor, significant, critical
    ) -> ScoreUpdate:
        """修正公開に基づくスコア更新"""
        
        # 修正タイプに基づいて調整
        adjustments = {
            "minor": -0.02,
            "significant": -0.05,
            "critical": -0.15
        }
        
        adjustment = adjustments.get(correction_type, -0.05) * self.sensitivity
        new_score = max(0.0, min(current_score + adjustment, 1.0))
        
        update = ScoreUpdate(
            source_id=source_id,
            old_score=current_score,
            new_score=new_score,
            score_change=new_score - current_score,
            update_reason=UpdateReason.CORRECTION_PUBLISHED,
            notes=f"Correction type: {correction_type}"
        )
        
        self.updates_history.append(update)
        self.source_scores[source_id] = new_score
        
        self._check_and_generate_alerts(source_id, update)
        
        return update
    
    def update_score_on_retraction(
        self,
        source_id: str,
        current_score: float,
        retraction_severity: str = "moderate"  # minor, moderate, severe
    ) -> ScoreUpdate:
        """撤回に基づくスコア更新"""
        
        # 撤回の重大度に基づいて調整
        adjustments = {
            "minor": -0.05,
            "moderate": -0.15,
            "severe": -0.25
        }
        
        adjustment = adjustments.get(retraction_severity, -0.15) * self.sensitivity
        new_score = max(0.0, min(current_score + adjustment, 1.0))
        
        update = ScoreUpdate(
            source_id=source_id,
            old_score=current_score,
            new_score=new_score,
            score_change=new_score - current_score,
            update_reason=UpdateReason.RETRACTION_ISSUED,
            notes=f"Retraction severity: {retraction_severity}"
        )
        
        self.updates_history.append(update)
        self.source_scores[source_id] = new_score
        
        self._check_and_generate_alerts(source_id, update)
        
        return update
    
    def update_score_on_accuracy_trend(
        self,
        source_id: str,
        current_score: float,
        trend: str,  # improving, stable, declining
        trend_strength: float = 0.5  # 0.0-1.0
    ) -> ScoreUpdate:
        """精度トレンドに基づくスコア更新"""
        
        trend_map = {
            "improving": (0.08, UpdateReason.ACCURACY_IMPROVEMENT),
            "stable": (0.0, UpdateReason.PERIODIC_REVIEW),
            "declining": (-0.12, UpdateReason.ACCURACY_DECLINE)
        }
        
        adjustment_base, reason = trend_map.get(trend, (0.0, UpdateReason.PERIODIC_REVIEW))
        adjustment = adjustment_base * self.sensitivity * trend_strength
        
        new_score = max(0.0, min(current_score + adjustment, 1.0))
        
        update = ScoreUpdate(
            source_id=source_id,
            old_score=current_score,
            new_score=new_score,
            score_change=new_score - current_score,
            update_reason=reason,
            notes=f"Trend: {trend}, Strength: {trend_strength:.1f}"
        )
        
        self.updates_history.append(update)
        self.source_scores[source_id] = new_score
        
        self._check_and_generate_alerts(source_id, update)
        
        return update
    
    def apply_manual_adjustment(
        self,
        source_id: str,
        current_score: float,
        adjustment: float,
        reason: str
    ) -> ScoreUpdate:
        """手動調整を適用"""
        
        # 調整を制限
        max_adjustment = 0.1 * self.sensitivity
        adjustment = max(-max_adjustment, min(adjustment, max_adjustment))
        
        new_score = max(0.0, min(current_score + adjustment, 1.0))
        
        update = ScoreUpdate(
            source_id=source_id,
            old_score=current_score,
            new_score=new_score,
            score_change=adjustment,
            update_reason=UpdateReason.MANUAL_ADJUSTMENT,
            notes=reason
        )
        
        self.updates_history.append(update)
        self.source_scores[source_id] = new_score
        
        self._check_and_generate_alerts(source_id, update)
        
        return update
    
    def _check_and_generate_alerts(self, source_id: str, update: ScoreUpdate):
        """アラート条件を確認して生成"""
        
        # 大きな負の変更
        if update.score_change < -0.15:
            alert = Alert(
                source_id=source_id,
                alert_level=AlertLevel.CRITICAL,
                message=f"Major credibility drop for source {source_id}: "
                        f"{update.old_score:.2f} → {update.new_score:.2f}"
            )
            self.alerts.append(alert)
        
        # 中程度の負の変更
        elif update.score_change < -0.05:
            alert = Alert(
                source_id=source_id,
                alert_level=AlertLevel.WARNING,
                message=f"Credibility decline for source {source_id}: "
                        f"{update.old_score:.2f} → {update.new_score:.2f}"
            )
            self.alerts.append(alert)
        
        # 大きな正の変更（重要）
        if update.score_change > 0.10:
            alert = Alert(
                source_id=source_id,
                alert_level=AlertLevel.INFO,
                message=f"Significant credibility improvement for {source_id}: "
                        f"{update.old_score:.2f} → {update.new_score:.2f}"
            )
            self.alerts.append(alert)
        
        # 低スコア警告
        if update.new_score < 0.4:
            alert = Alert(
                source_id=source_id,
                alert_level=AlertLevel.WARNING,
                message=f"Source {source_id} credibility is low: {update.new_score:.2f}"
            )
            self.alerts.append(alert)
    
    def get_update_history(
        self,
        source_id: Optional[str] = None,
        max_records: int = 100
    ) -> List[ScoreUpdate]:
        """更新履歴を取得"""
        
        if source_id:
            history = [u for u in self.updates_history if u.source_id == source_id]
        else:
            history = self.updates_history
        
        # 最新の更新を取得
        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:max_records]
    
    def get_score_trend_analysis(
        self,
        source_id: str,
        window_days: int = 30
    ) -> Dict:
        """スコアトレンド分析"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)
        
        relevant_updates = [
            u for u in self.updates_history
            if u.source_id == source_id and u.timestamp >= cutoff_date
        ]
        
        if not relevant_updates:
            return {
                "source_id": source_id,
                "period_days": window_days,
                "updates_count": 0,
                "trend": "insufficient_data",
                "average_change": 0.0
            }
        
        changes = [u.score_change for u in relevant_updates]
        
        # トレンドを判定
        avg_change = statistics.mean(changes)
        if avg_change > 0.02:
            trend = "improving"
        elif avg_change < -0.02:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "source_id": source_id,
            "period_days": window_days,
            "updates_count": len(relevant_updates),
            "trend": trend,
            "average_change": avg_change,
            "total_change": sum(changes),
            "min_score": min([u.new_score for u in relevant_updates]),
            "max_score": max([u.new_score for u in relevant_updates]),
            "latest_score": relevant_updates[-1].new_score if relevant_updates else None
        }
    
    def get_active_alerts(self) -> List[Alert]:
        """アクティブなアラートを取得"""
        return [a for a in self.alerts if not a.addressed]
    
    def get_alerts_by_level(self, level: AlertLevel) -> List[Alert]:
        """レベル別にアラートを取得"""
        return [a for a in self.alerts if a.alert_level == level]
    
    def address_alert(self, alert_index: int, response: str) -> bool:
        """アラートに対応"""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].addressed = True
            self.alerts[alert_index].response = response
            return True
        return False
    
    def get_statistics(self) -> UpdateStatistics:
        """更新統計を取得"""
        
        if not self.updates_history:
            return UpdateStatistics(
                total_updates=0,
                average_score_change=0.0,
                max_positive_change=0.0,
                max_negative_change=0.0,
                updates_by_reason={},
                sources_improved=0,
                sources_declined=0,
                active_alerts=0,
                total_alerts=0
            )
        
        changes = [u.score_change for u in self.updates_history]
        
        # 理由別の集計
        updates_by_reason = {}
        for update in self.updates_history:
            reason = update.update_reason.value
            updates_by_reason[reason] = updates_by_reason.get(reason, 0) + 1
        
        # 改善・悪化の集計
        sources_improved = len(set(u.source_id for u in self.updates_history if u.score_change > 0))
        sources_declined = len(set(u.source_id for u in self.updates_history if u.score_change < 0))
        
        # アラートの集計
        active_alerts = len(self.get_active_alerts())
        total_alerts = len(self.alerts)
        
        return UpdateStatistics(
            total_updates=len(self.updates_history),
            average_score_change=statistics.mean(changes),
            max_positive_change=max(changes),
            max_negative_change=min(changes),
            updates_by_reason=updates_by_reason,
            sources_improved=sources_improved,
            sources_declined=sources_declined,
            active_alerts=active_alerts,
            total_alerts=total_alerts
        )
    
    def generate_report(self) -> str:
        """更新エンジンレポートを生成"""
        stats = self.get_statistics()
        
        report = []
        report.append("=" * 60)
        report.append("CREDIBILITY SCORE UPDATER REPORT")
        report.append(f"Generated: {datetime.utcnow().isoformat()}")
        report.append("=" * 60)
        report.append("")
        
        # 概要
        report.append("SUMMARY")
        report.append("-" * 60)
        report.append(f"Total Updates: {stats.total_updates}")
        report.append(f"Average Score Change: {stats.average_score_change:+.3f}")
        report.append(f"Max Positive Change: {stats.max_positive_change:.3f}")
        report.append(f"Max Negative Change: {stats.max_negative_change:.3f}")
        report.append("")
        
        # 更新タイプ
        report.append("UPDATES BY REASON")
        report.append("-" * 60)
        for reason, count in sorted(stats.updates_by_reason.items(), key=lambda x: x[1], reverse=True):
            report.append(f"{reason}: {count}")
        report.append("")
        
        # ソース情報
        report.append("SOURCE IMPACT")
        report.append("-" * 60)
        report.append(f"Sources Improved: {stats.sources_improved}")
        report.append(f"Sources Declined: {stats.sources_declined}")
        report.append("")
        
        # アラート
        report.append("ALERTS")
        report.append("-" * 60)
        report.append(f"Active Alerts: {stats.active_alerts}/{stats.total_alerts}")
        
        if stats.active_alerts > 0:
            critical = len(self.get_alerts_by_level(AlertLevel.CRITICAL))
            warning = len(self.get_alerts_by_level(AlertLevel.WARNING))
            info = len(self.get_alerts_by_level(AlertLevel.INFO))
            report.append(f"  - Critical: {critical}")
            report.append(f"  - Warning: {warning}")
            report.append(f"  - Info: {info}")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
