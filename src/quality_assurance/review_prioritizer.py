"""
レビュー優先度判定・専門家マッチングエンジン

レビュー項目の優先度を自動判定し、
最適な専門家に割当を最適化するシステム
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import statistics


class PriorityLevel(Enum):
    """優先度レベル"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UrgencyLevel(Enum):
    """緊急度レベル"""
    IMMEDIATE = "immediate"  # <24時間
    URGENT = "urgent"  # 1-3日
    NORMAL = "normal"  # 3-7日
    FLEXIBLE = "flexible"  # >7日


@dataclass
class ReviewItem:
    """レビュー項目"""
    item_id: str
    item_type: str  # source, claim, fact
    content: str
    
    required_expertise: List[str]
    min_expertise_level: Optional[str] = None
    
    created_date: datetime = None
    deadline: Optional[datetime] = None
    
    priority_keywords: List[str] = None
    related_items: List[str] = None
    
    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.utcnow()
        if self.priority_keywords is None:
            self.priority_keywords = []
        if self.related_items is None:
            self.related_items = []


@dataclass
class PriorityScore:
    """優先度スコア"""
    item_id: str
    
    urgency_score: float  # 0-1
    importance_score: float  # 0-1
    complexity_score: float  # 0-1
    risk_score: float  # 0-1
    
    final_priority_score: float  # 0-1
    priority_level: PriorityLevel
    urgency_level: UrgencyLevel
    
    justification: str


@dataclass
class MatchScore:
    """マッチスコア"""
    expert_id: str
    item_id: str
    
    expertise_match: float  # 0-1
    availability_score: float  # 0-1
    performance_score: float  # 0-1
    workload_score: float  # 0-1
    
    final_match_score: float  # 0-1
    
    match_confidence: float
    recommendation: str


class ReviewPrioritizer:
    """レビュー優先度判定・マッチングエンジン"""
    
    def __init__(self):
        """初期化"""
        self.priority_cache: Dict[str, PriorityScore] = {}
        self.match_cache: Dict[str, Dict[str, MatchScore]] = {}  # item_id -> {expert_id: score}
    
    def calculate_priority(
        self,
        item: ReviewItem,
        urgency_factor: float = 0.3,
        importance_factor: float = 0.4,
        complexity_factor: float = 0.2,
        risk_factor: float = 0.1
    ) -> PriorityScore:
        """レビュー項目の優先度を計算"""
        
        # 緊急度スコアを計算
        urgency_score = self._calculate_urgency_score(item.deadline)
        urgency_level = self._determine_urgency_level(item.deadline)
        
        # 重要度スコアを計算
        importance_score = self._calculate_importance_score(
            item.item_type,
            item.priority_keywords
        )
        
        # 複雑度スコアを計算
        complexity_score = self._calculate_complexity_score(
            len(item.required_expertise),
            len(item.content)
        )
        
        # リスクスコアを計算
        risk_score = self._calculate_risk_score(
            item.item_type,
            item.priority_keywords
        )
        
        # 最終スコアを計算（加重平均）
        final_score = (
            urgency_score * urgency_factor +
            importance_score * importance_factor +
            complexity_score * complexity_factor +
            risk_score * risk_factor
        )
        
        # 優先度レベルを判定
        priority_level = self._determine_priority_level(final_score)
        
        # 正当化理由を生成
        justification = self._generate_justification(
            urgency_score,
            importance_score,
            complexity_score,
            risk_score
        )
        
        priority_score = PriorityScore(
            item_id=item.item_id,
            urgency_score=urgency_score,
            importance_score=importance_score,
            complexity_score=complexity_score,
            risk_score=risk_score,
            final_priority_score=final_score,
            priority_level=priority_level,
            urgency_level=urgency_level,
            justification=justification
        )
        
        self.priority_cache[item.item_id] = priority_score
        return priority_score
    
    def _calculate_urgency_score(self, deadline: Optional[datetime]) -> float:
        """緊急度スコアを計算"""
        if deadline is None:
            return 0.3  # デフォルト
        
        now = datetime.utcnow()
        hours_until_deadline = (deadline - now).total_seconds() / 3600
        
        if hours_until_deadline <= 0:
            return 1.0  # 期限超過
        elif hours_until_deadline <= 24:
            return 0.9  # 24時間以内
        elif hours_until_deadline <= 72:
            return 0.7  # 3日以内
        elif hours_until_deadline <= 168:
            return 0.5  # 7日以内
        else:
            return 0.2  # 7日以上
    
    def _determine_urgency_level(self, deadline: Optional[datetime]) -> UrgencyLevel:
        """緊急度レベルを判定"""
        if deadline is None:
            return UrgencyLevel.FLEXIBLE
        
        now = datetime.utcnow()
        hours_until_deadline = (deadline - now).total_seconds() / 3600
        
        if hours_until_deadline <= 24:
            return UrgencyLevel.IMMEDIATE
        elif hours_until_deadline <= 72:
            return UrgencyLevel.URGENT
        elif hours_until_deadline <= 168:
            return UrgencyLevel.NORMAL
        else:
            return UrgencyLevel.FLEXIBLE
    
    def _calculate_importance_score(
        self,
        item_type: str,
        priority_keywords: List[str]
    ) -> float:
        """重要度スコアを計算"""
        
        # アイテムタイプの重要度
        type_scores = {
            "source": 0.6,
            "claim": 0.7,
            "fact": 0.8,
            "viral": 0.9
        }
        
        score = type_scores.get(item_type, 0.5)
        
        # キーワードボーナス
        critical_keywords = ["breaking", "urgent", "viral", "controversy"]
        if any(kw in str(priority_keywords).lower() for kw in critical_keywords):
            score = min(score + 0.2, 1.0)
        
        return score
    
    def _calculate_complexity_score(
        self,
        num_expertise: int,
        content_length: int
    ) -> float:
        """複雑度スコアを計算"""
        
        # 必要な専門領域の数による複雑度
        expertise_score = min(num_expertise / 3.0, 1.0)  # 3領域でmax
        
        # コンテンツの複雑度
        content_score = min(content_length / 1000.0, 0.5)  # 1000文字でmax 0.5
        
        return (expertise_score * 0.6) + (content_score * 0.4)
    
    def _calculate_risk_score(
        self,
        item_type: str,
        priority_keywords: List[str]
    ) -> float:
        """リスクスコアを計算"""
        
        risk_keywords = ["misinformation", "false", "fake", "scam", "dangerous", "harmful"]
        
        score = 0.3  # ベーススコア
        
        if any(kw in str(priority_keywords).lower() for kw in risk_keywords):
            score += 0.4
        
        if item_type == "viral":
            score += 0.2
        
        return min(score, 1.0)
    
    def _determine_priority_level(self, score: float) -> PriorityLevel:
        """優先度レベルを判定"""
        if score >= 0.8:
            return PriorityLevel.CRITICAL
        elif score >= 0.6:
            return PriorityLevel.HIGH
        elif score >= 0.4:
            return PriorityLevel.MEDIUM
        else:
            return PriorityLevel.LOW
    
    def _generate_justification(
        self,
        urgency: float,
        importance: float,
        complexity: float,
        risk: float
    ) -> str:
        """正当化理由を生成"""
        
        factors = []
        if urgency > 0.7:
            factors.append("high urgency")
        if importance > 0.7:
            factors.append("high importance")
        if complexity > 0.6:
            factors.append("high complexity")
        if risk > 0.6:
            factors.append("high risk")
        
        if not factors:
            return "Standard review priority"
        
        return f"Priority due to: {', '.join(factors)}"
    
    def find_best_match(
        self,
        item: ReviewItem,
        available_experts: List,  # ExpertProfile list
        expert_performances: Dict  # expert_id -> ExpertPerformance
    ) -> Optional[MatchScore]:
        """最適な専門家をマッチング"""
        
        if not available_experts:
            return None
        
        best_match = None
        best_score = 0.0
        
        for expert in available_experts:
            match_score = self._calculate_match_score(
                expert,
                item,
                expert_performances.get(expert.expert_id)
            )
            
            if match_score.final_match_score > best_score:
                best_score = match_score.final_match_score
                best_match = match_score
        
        return best_match
    
    def _calculate_match_score(
        self,
        expert,
        item: ReviewItem,
        performance
    ) -> MatchScore:
        """マッチスコアを計算"""
        
        # 専門知識マッチスコア
        expertise_match = self._calculate_expertise_match(expert, item)
        
        # 可用性スコア
        availability_score = 1.0 if expert.current_active_reviews == 0 else \
                            1.0 - (expert.current_active_reviews / expert.max_concurrent_reviews)
        
        # パフォーマンススコア
        performance_score = 0.5  # デフォルト
        if performance:
            performance_score = (
                performance.accuracy_score * 0.4 +
                performance.reliability_score * 0.4 +
                performance.feedback_score * 0.2
            )
        
        # ワークロードスコア
        workload_factor = 1.0 - (expert.current_active_reviews / expert.max_concurrent_reviews)
        workload_score = workload_factor * availability_score
        
        # 最終スコア
        final_score = (
            expertise_match * 0.4 +
            availability_score * 0.2 +
            performance_score * 0.3 +
            workload_score * 0.1
        )
        
        match_score = MatchScore(
            expert_id=expert.expert_id,
            item_id=item.item_id,
            expertise_match=expertise_match,
            availability_score=availability_score,
            performance_score=performance_score,
            workload_score=workload_score,
            final_match_score=final_score,
            match_confidence=min(final_score * 1.2, 1.0),
            recommendation="Recommended" if final_score > 0.7 else "Consider"
        )
        
        return match_score
    
    def _calculate_expertise_match(self, expert, item: ReviewItem) -> float:
        """専門知識マッチスコアを計算"""
        
        match_areas = set(expert.expertise_areas) & set(item.required_expertise)
        
        if not item.required_expertise:
            return 0.5  # デフォルト
        
        match_ratio = len(match_areas) / len(item.required_expertise)
        
        # レベルチェック
        level_bonus = 0.0
        if item.min_expertise_level:
            for area in match_areas:
                exp_level = expert.expertise_levels.get(area)
                if exp_level and str(exp_level.value) >= item.min_expertise_level:
                    level_bonus += 0.1
        
        return min(match_ratio + level_bonus, 1.0)
    
    def rank_candidates(
        self,
        item: ReviewItem,
        available_experts: List,
        expert_performances: Dict
    ) -> List[MatchScore]:
        """複数の専門家候補を順位付け"""
        
        matches = []
        for expert in available_experts:
            match = self._calculate_match_score(expert, item, expert_performances.get(expert.expert_id))
            matches.append(match)
        
        # スコアでソート
        matches.sort(key=lambda m: m.final_match_score, reverse=True)
        
        return matches
    
    def generate_assignment_report(
        self,
        priority_score: PriorityScore,
        top_matches: List[MatchScore]
    ) -> str:
        """割当レポートを生成"""
        
        report = []
        report.append("=" * 60)
        report.append(f"REVIEW ASSIGNMENT REPORT")
        report.append(f"Item: {priority_score.item_id}")
        report.append("=" * 60)
        report.append("")
        
        # 優先度情報
        report.append("PRIORITY ASSESSMENT")
        report.append("-" * 60)
        report.append(f"Priority Level: {priority_score.priority_level.value}")
        report.append(f"Priority Score: {priority_score.final_priority_score:.2%}")
        report.append(f"Urgency: {priority_score.urgency_level.value}")
        report.append(f"Justification: {priority_score.justification}")
        report.append("")
        
        # マッチング結果
        report.append("TOP CANDIDATES")
        report.append("-" * 60)
        for i, match in enumerate(top_matches[:3], 1):
            report.append(f"{i}. Expert {match.expert_id}")
            report.append(f"   Match Score: {match.final_match_score:.2%}")
            report.append(f"   Recommendation: {match.recommendation}")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
