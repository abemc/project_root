"""
情報源信頼性分析エンジン

情報源の信頼性を定量的に評価し、検証結果に基づいて
信頼性スコアを動的に更新する統合システム
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import statistics


class CredibilityLevel(Enum):
    """信頼性レベル"""
    TRUSTED = "TRUSTED"  # スコア 0.8-1.0
    CREDIBLE = "CREDIBLE"  # スコア 0.6-0.8
    UNCERTAIN = "UNCERTAIN"  # スコア 0.4-0.6
    UNRELIABLE = "UNRELIABLE"  # スコア 0.0-0.4


class CorrectionTrend(Enum):
    """修正トレンド"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class AuthorInfo:
    """著者情報"""
    name: str
    expertise_areas: List[str] = field(default_factory=list)
    credentials: List[str] = field(default_factory=list)
    h_index: Optional[float] = None
    publication_count: Optional[int] = None


@dataclass
class SourceMetadata:
    """情報源メタデータ"""
    source_id: str
    domain: str
    organization: str
    publish_date: Optional[datetime] = None
    author_info: Optional[AuthorInfo] = None
    certifications: List[str] = field(default_factory=list)
    country: Optional[str] = None
    language: Optional[str] = None
    website_rank: Optional[int] = None
    social_followers: Optional[int] = None


@dataclass
class AccuracyHistory:
    """精度履歴"""
    source_id: str
    total_claims: int = 0
    correct_claims: int = 0
    incorrect_claims: int = 0
    retracted_claims: int = 0
    corrected_claims: int = 0
    claims_with_warnings: int = 0
    accuracy_rate: float = 0.0
    last_major_error: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    def __post_init__(self):
        """初期化後処理"""
        self._update_accuracy_rate()
    
    def _update_accuracy_rate(self):
        """精度率を更新"""
        if self.total_claims > 0:
            self.accuracy_rate = self.correct_claims / self.total_claims
        else:
            self.accuracy_rate = 0.0
    
    def add_correct_claim(self):
        """正確なクレームを追加"""
        self.total_claims += 1
        self.correct_claims += 1
        self._update_accuracy_rate()
    
    def add_incorrect_claim(self, is_major: bool = False):
        """不正確なクレームを追加"""
        self.total_claims += 1
        self.incorrect_claims += 1
        if is_major:
            self.last_major_error = datetime.utcnow()
        self._update_accuracy_rate()
    
    def add_retracted_claim(self):
        """取り下げられたクレームを追加"""
        self.total_claims += 1
        self.retracted_claims += 1
        self._update_accuracy_rate()
    
    def add_corrected_claim(self):
        """修正されたクレームを追加"""
        self.total_claims += 1
        self.corrected_claims += 1
        self._update_accuracy_rate()
    
    @property
    def correction_trend(self) -> CorrectionTrend:
        """修正トレンドを推定"""
        if self.total_claims < 5:
            return CorrectionTrend.INSUFFICIENT_DATA
        
        recent_error_rate = (self.incorrect_claims + self.retracted_claims) / self.total_claims
        
        if self.last_major_error:
            days_since_error = (datetime.utcnow() - self.last_major_error).days
            if days_since_error > 180:  # 半年以上前
                return CorrectionTrend.IMPROVING
        
        if recent_error_rate < 0.05:
            return CorrectionTrend.STABLE
        elif recent_error_rate > 0.20:
            return CorrectionTrend.DECLINING
        else:
            return CorrectionTrend.STABLE
    
    @property
    def correction_responsiveness(self) -> float:
        """修正への対応性（0-1）"""
        if self.incorrect_claims == 0:
            return 1.0
        
        response_rate = self.corrected_claims / (self.incorrect_claims + self.retracted_claims + 0.001)
        return min(response_rate, 1.0)


@dataclass
class ReputationScore:
    """評判スコア"""
    third_party_ratings: List[float] = field(default_factory=list)
    news_sentiment: float = 0.5  # -1 to 1
    academic_citations: int = 0
    award_count: int = 0
    lawsuit_count: int = 0
    retraction_index: float = 0.0
    
    @property
    def composite_score(self) -> float:
        """複合評判スコア（0-1）"""
        scores = []
        
        # 第三者レーティング
        if self.third_party_ratings:
            avg_rating = statistics.mean(self.third_party_ratings)
            scores.append(avg_rating)
        
        # ニュース感情
        news_score = (self.news_sentiment + 1) / 2  # -1,1 -> 0,1
        scores.append(news_score * 0.5)  # ウェイト50%
        
        # 学術引用
        citation_score = min(self.academic_citations / 100, 1.0)
        scores.append(citation_score * 0.3)  # ウェイト30%
        
        # 賞
        award_score = min(self.award_count / 10, 1.0)
        scores.append(award_score * 0.2)  # ウェイト20%
        
        # 訴訟
        lawsuit_penalty = min(self.lawsuit_count * 0.1, 0.3)
        scores.append(max(1.0 - lawsuit_penalty, 0.0) * 0.2)  # ウェイト20%
        
        # 撤回指数
        retraction_penalty = self.retraction_index * 0.2
        scores.append(max(1.0 - retraction_penalty, 0.0) * 0.1)  # ウェイト10%
        
        return statistics.mean(scores) if scores else 0.5


@dataclass
class CredibilityAnalysisResult:
    """信頼性分析結果"""
    source_id: str
    metadata: SourceMetadata
    accuracy_history: AccuracyHistory
    reputation_score: ReputationScore
    
    base_credibility_score: float  # メタデータに基づく基本スコア
    history_credibility_score: float  # 履歴に基づくスコア
    reputation_credibility_score: float  # 評判に基づくスコア
    
    final_credibility_score: float  # 最終スコア（0-1）
    credibility_level: CredibilityLevel
    
    confidence: float  # 信頼度（データ量に基づく）
    recommendations: List[str] = field(default_factory=list)
    
    confidence_factors: Dict[str, float] = field(default_factory=dict)
    trend_analysis: Dict[str, str] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SourceCredibilityAnalyzer:
    """情報源信頼性分析エンジン"""
    
    def __init__(self):
        """初期化"""
        self.metadata_cache: Dict[str, SourceMetadata] = {}
        self.accuracy_cache: Dict[str, AccuracyHistory] = {}
        self.reputation_cache: Dict[str, ReputationScore] = {}
    
    def analyze_credibility(
        self,
        source_id: str,
        metadata: Optional[SourceMetadata] = None,
        accuracy_history: Optional[AccuracyHistory] = None,
        reputation_score: Optional[ReputationScore] = None
    ) -> CredibilityAnalysisResult:
        """信頼性を総合的に分析"""
        
        # キャッシュまたは提供されたデータを使用
        meta = metadata or self.metadata_cache.get(source_id, self._create_default_metadata(source_id))
        history = accuracy_history or self.accuracy_cache.get(source_id, AccuracyHistory(source_id))
        reputation = reputation_score or self.reputation_cache.get(source_id, ReputationScore())
        
        # キャッシュを更新
        self.metadata_cache[source_id] = meta
        self.accuracy_cache[source_id] = history
        self.reputation_cache[source_id] = reputation
        
        # 各ドメインのスコアを計算
        base_score = self._calculate_base_credibility_score(meta)
        history_score = self._calculate_history_credibility_score(history)
        reputation_score_val = reputation.composite_score
        
        # 最終スコアを計算
        final_score = self._calculate_final_score(base_score, history_score, reputation_score_val)
        
        # 信頼性レベルを判定
        credibility_level = self._determine_credibility_level(final_score)
        
        # 信頼度を計算
        confidence = self._calculate_confidence(history, meta, reputation)
        
        # 推奨事項を生成
        recommendations = self._generate_recommendations(
            final_score, history, reputation, credibility_level
        )
        
        # 信頼度ファクターを計算
        confidence_factors = {
            "data_points": min(history.total_claims / 100, 1.0),
            "time_coverage": self._calculate_time_coverage(history),
            "source_maturity": self._calculate_source_maturity(meta),
            "correction_responsiveness": history.correction_responsiveness
        }
        
        # トレンド分析
        trend_analysis = {
            "accuracy_trend": history.correction_trend.value,
            "recent_performance": self._analyze_recent_performance(history),
            "reputation_trend": self._analyze_reputation_trend(reputation)
        }
        
        result = CredibilityAnalysisResult(
            source_id=source_id,
            metadata=meta,
            accuracy_history=history,
            reputation_score=reputation,
            base_credibility_score=base_score,
            history_credibility_score=history_score,
            reputation_credibility_score=reputation_score_val,
            final_credibility_score=final_score,
            credibility_level=credibility_level,
            confidence=confidence,
            recommendations=recommendations,
            confidence_factors=confidence_factors,
            trend_analysis=trend_analysis
        )
        
        return result
    
    def _calculate_base_credibility_score(self, metadata: SourceMetadata) -> float:
        """メタデータに基づく基本スコアを計算"""
        score = 0.5
        
        # ドメイン信頼性
        if metadata.domain:
            if any(x in metadata.domain for x in [".edu", ".gov", ".org"]):
                score += 0.15
            elif ".com" in metadata.domain:
                score += 0.05
        
        # 組織情報
        if metadata.organization:
            score += 0.1
        
        # 著者情報
        if metadata.author_info:
            author_score = 0.0
            if metadata.author_info.h_index and metadata.author_info.h_index > 0:
                author_score += min(metadata.author_info.h_index / 50, 0.1)
            if metadata.author_info.credentials:
                author_score += 0.05
            if metadata.author_info.publication_count and metadata.author_info.publication_count > 10:
                author_score += 0.05
            score += author_score
        
        # 認定資格
        if metadata.certifications:
            score += 0.1
        
        # ウェブサイトランキング
        if metadata.website_rank:
            if metadata.website_rank < 10000:
                score += 0.15
            elif metadata.website_rank < 100000:
                score += 0.08
        
        # ソーシャルフォロワー
        if metadata.social_followers:
            if metadata.social_followers > 100000:
                score += 0.1
            elif metadata.social_followers > 10000:
                score += 0.05
        
        return min(score, 1.0)
    
    def _calculate_history_credibility_score(self, history: AccuracyHistory) -> float:
        """履歴に基づくスコアを計算"""
        
        # 基本精度率
        if history.total_claims == 0:
            return 0.5
        
        base_score = history.accuracy_rate
        
        # 修正への対応性
        correction_bonus = history.correction_responsiveness * 0.2
        
        # 取り下げペナルティ
        retraction_penalty = (history.retracted_claims / (history.total_claims + 1)) * 0.15
        
        # 修正トレンド
        trend_bonus = 0.0
        if history.correction_trend == CorrectionTrend.IMPROVING:
            trend_bonus = 0.1
        elif history.correction_trend == CorrectionTrend.DECLINING:
            trend_bonus = -0.15
        
        score = base_score + correction_bonus - retraction_penalty + trend_bonus
        
        return max(min(score, 1.0), 0.0)
    
    def _calculate_final_score(
        self,
        base_score: float,
        history_score: float,
        reputation_score: float
    ) -> float:
        """最終スコアを計算"""
        # ウェイト: 基本30%, 履歴50%, 評判20%
        return (base_score * 0.3) + (history_score * 0.5) + (reputation_score * 0.2)
    
    def _determine_credibility_level(self, score: float) -> CredibilityLevel:
        """信頼性レベルを判定"""
        if score >= 0.8:
            return CredibilityLevel.TRUSTED
        elif score >= 0.6:
            return CredibilityLevel.CREDIBLE
        elif score >= 0.4:
            return CredibilityLevel.UNCERTAIN
        else:
            return CredibilityLevel.UNRELIABLE
    
    def _calculate_confidence(
        self,
        history: AccuracyHistory,
        metadata: SourceMetadata,
        reputation: ReputationScore
    ) -> float:
        """信頼度を計算（0-1）"""
        confidence = 0.5
        
        # データポイント数
        if history.total_claims > 50:
            confidence += 0.25
        elif history.total_claims > 20:
            confidence += 0.15
        elif history.total_claims > 5:
            confidence += 0.05
        
        # メタデータの充実度
        meta_completeness = 0.0
        if metadata.author_info:
            meta_completeness += 0.1
        if metadata.certifications:
            meta_completeness += 0.1
        if metadata.website_rank:
            meta_completeness += 0.1
        confidence += meta_completeness * 0.1
        
        # 評判情報
        if reputation.third_party_ratings:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _calculate_time_coverage(self, history: AccuracyHistory) -> float:
        """時間カバレッジを計算"""
        if not history.last_updated:
            return 0.0
        
        days_covered = (datetime.utcnow() - history.last_updated).days
        coverage = min(days_covered / 365, 1.0)
        
        return coverage
    
    def _calculate_source_maturity(self, metadata: SourceMetadata) -> float:
        """ソース成熟度を計算"""
        if metadata.publish_date:
            days_active = (datetime.utcnow() - metadata.publish_date).days
            maturity = min(days_active / (365 * 5), 1.0)  # 5年でmax
            return maturity
        
        return 0.3
    
    def _analyze_recent_performance(self, history: AccuracyHistory) -> str:
        """最近のパフォーマンスを分析"""
        if history.total_claims < 5:
            return "insufficient_data"
        
        recent_accuracy = history.accuracy_rate
        
        if recent_accuracy >= 0.9:
            return "excellent"
        elif recent_accuracy >= 0.75:
            return "good"
        elif recent_accuracy >= 0.5:
            return "moderate"
        else:
            return "poor"
    
    def _analyze_reputation_trend(self, reputation: ReputationScore) -> str:
        """評判トレンドを分析"""
        if not reputation.third_party_ratings:
            return "unknown"
        
        recent_avg = statistics.mean(reputation.third_party_ratings[-3:])
        
        if recent_avg >= 0.8:
            return "positive"
        elif recent_avg >= 0.6:
            return "neutral"
        else:
            return "negative"
    
    def _generate_recommendations(
        self,
        score: float,
        history: AccuracyHistory,
        reputation: ReputationScore,
        level: CredibilityLevel
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        # スコアに基づく推奨
        if score < 0.5:
            recommendations.append("Sources require enhanced verification before use")
            recommendations.append("Consider cross-referencing with trusted sources")
        
        # 精度に基づく推奨
        if history.total_claims > 0:
            if history.accuracy_rate < 0.7:
                recommendations.append("Source shows lower accuracy rate in history")
                recommendations.append("Individual claims should be fact-checked")
        
        # 修正トレンドに基づく推奨
        if history.correction_trend == CorrectionTrend.DECLINING:
            recommendations.append("Source credibility appears to be declining")
            recommendations.append("Use with increased caution")
        elif history.correction_trend == CorrectionTrend.IMPROVING:
            recommendations.append("Source shows improving trend in recent performance")
        
        # 評判に基づく推奨
        if reputation.lawsuit_count > 5:
            recommendations.append("Source has legal disputes in history")
        
        if reputation.retraction_index > 0.1:
            recommendations.append("Source has significant retraction history")
        
        # デフォルト推奨
        if not recommendations:
            if level == CredibilityLevel.TRUSTED:
                recommendations.append("Source is considered trusted")
            elif level == CredibilityLevel.CREDIBLE:
                recommendations.append("Source is generally credible")
            else:
                recommendations.append("Use standard verification procedures")
        
        return recommendations
    
    def _create_default_metadata(self, source_id: str) -> SourceMetadata:
        """デフォルトメタデータを作成"""
        return SourceMetadata(
            source_id=source_id,
            domain=source_id if "." in source_id else f"{source_id}.com",
            organization=source_id
        )
    
    def get_score_interpretation(self, score: float) -> str:
        """スコアの解釈を取得"""
        level = self._determine_credibility_level(score)
        
        interpretations = {
            CredibilityLevel.TRUSTED: f"Highly credible source ({score:.1%}) - Suitable for critical applications",
            CredibilityLevel.CREDIBLE: f"Generally credible source ({score:.1%}) - Standard verification recommended",
            CredibilityLevel.UNCERTAIN: f"Uncertain credibility ({score:.1%}) - Enhanced verification required",
            CredibilityLevel.UNRELIABLE: f"Low credibility ({score:.1%}) - Use with extreme caution"
        }
        
        return interpretations.get(level, "Unknown credibility level")
    
    def generate_report(self, result: CredibilityAnalysisResult) -> str:
        """分析結果のレポートを生成"""
        report = []
        report.append("=" * 60)
        report.append("SOURCE CREDIBILITY ANALYSIS REPORT")
        report.append(f"Source ID: {result.source_id}")
        report.append(f"Analyzed: {result.timestamp.isoformat()}")
        report.append("=" * 60)
        report.append("")
        
        # 概要
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 60)
        report.append(f"Final Credibility Score: {result.final_credibility_score:.2f}/1.0")
        report.append(f"Credibility Level: {result.credibility_level.value}")
        report.append(f"Confidence: {result.confidence:.1%}")
        report.append("")
        
        # スコア内訳
        report.append("SCORE BREAKDOWN")
        report.append("-" * 60)
        report.append(f"Base Credibility (Metadata): {result.base_credibility_score:.2f}")
        report.append(f"History Credibility: {result.history_credibility_score:.2f}")
        report.append(f"Reputation Credibility: {result.reputation_credibility_score:.2f}")
        report.append("")
        
        # 履歴分析
        report.append("ACCURACY HISTORY")
        report.append("-" * 60)
        report.append(f"Total Claims: {result.accuracy_history.total_claims}")
        report.append(f"Correct: {result.accuracy_history.correct_claims}")
        report.append(f"Incorrect: {result.accuracy_history.incorrect_claims}")
        report.append(f"Accuracy Rate: {result.accuracy_history.accuracy_rate:.1%}")
        report.append(f"Correction Trend: {result.accuracy_history.correction_trend.value}")
        report.append(f"Correction Responsiveness: {result.accuracy_history.correction_responsiveness:.1%}")
        report.append("")
        
        # メタデータ
        report.append("SOURCE METADATA")
        report.append("-" * 60)
        report.append(f"Domain: {result.metadata.domain}")
        report.append(f"Organization: {result.metadata.organization}")
        if result.metadata.website_rank:
            report.append(f"Website Rank: {result.metadata.website_rank}")
        if result.metadata.social_followers:
            report.append(f"Social Followers: {result.metadata.social_followers}")
        report.append("")
        
        # 推奨事項
        report.append("RECOMMENDATIONS")
        report.append("-" * 60)
        for i, rec in enumerate(result.recommendations, 1):
            report.append(f"{i}. {rec}")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
