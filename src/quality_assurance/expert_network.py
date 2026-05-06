"""
専門家ネットワーク管理システム

専門家の管理、専門領域マッピング、可用性トラッキング、
パフォーマンス履歴記録を実現するシステム
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import uuid


class ExpertLevel(Enum):
    """専門家レベル"""
    JUNIOR = "junior"
    INTERMEDIATE = "intermediate"
    SENIOR = "senior"
    PRINCIPAL = "principal"


class AvailabilityStatus(Enum):
    """可用性ステータス"""
    AVAILABLE = "available"
    BUSY = "busy"
    ON_LEAVE = "on_leave"
    UNAVAILABLE = "unavailable"


@dataclass
class ExpertProfile:
    """専門家プロフィール"""
    expert_id: str
    name: str
    email: str
    affiliation: Optional[str] = None
    
    expertise_areas: List[str] = field(default_factory=list)
    expertise_levels: Dict[str, ExpertLevel] = field(default_factory=dict)
    certifications: List[str] = field(default_factory=list)
    
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    availability_from: Optional[datetime] = None
    availability_until: Optional[datetime] = None
    
    max_concurrent_reviews: int = 5
    current_active_reviews: int = 0
    
    languages: List[str] = field(default_factory=list)
    timezone: Optional[str] = None
    
    join_date: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExpertPerformance:
    """専門家パフォーマンス"""
    expert_id: str
    
    total_reviews: int = 0
    completed_reviews: int = 0
    average_review_time_hours: float = 0.0
    
    accuracy_score: float = 0.5  # 0-1
    reliability_score: float = 0.5  # 0-1
    feedback_score: float = 0.5  # 0-1
    
    revision_rate: float = 0.0  # 改版率
    approval_rate: float = 0.0  # 承認率
    
    specialization_areas: Dict[str, float] = field(default_factory=dict)
    
    last_performance_update: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReviewAssignment:
    """レビュー割当"""
    assignment_id: str
    expert_id: str
    item_id: str
    item_type: str  # source, claim, fact
    
    assigned_date: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    
    status: str = "pending"  # pending, in_progress, completed, skipped
    feedback: Optional[str] = None
    notes: Optional[str] = None


class ExpertNetworkManager:
    """専門家ネットワーク管理システム"""
    
    def __init__(self):
        """初期化"""
        self.experts: Dict[str, ExpertProfile] = {}
        self.performance: Dict[str, ExpertPerformance] = {}
        self.assignments: Dict[str, ReviewAssignment] = {}
        self.expertise_index: Dict[str, Set[str]] = {}  # expertise_area -> set(expert_ids)
    
    def register_expert(
        self,
        name: str,
        email: str,
        expertise_areas: List[str],
        affiliation: Optional[str] = None,
        certifications: Optional[List[str]] = None,
        languages: Optional[List[str]] = None
    ) -> ExpertProfile:
        """専門家を登録"""
        expert_id = str(uuid.uuid4())
        
        profile = ExpertProfile(
            expert_id=expert_id,
            name=name,
            email=email,
            affiliation=affiliation,
            expertise_areas=expertise_areas,
            certifications=certifications or [],
            languages=languages or ["English"]
        )
        
        # 専門領域ごとの初期レベルを設定
        for area in expertise_areas:
            profile.expertise_levels[area] = ExpertLevel.INTERMEDIATE
        
        self.experts[expert_id] = profile
        self.performance[expert_id] = ExpertPerformance(expert_id=expert_id)
        
        # インデックスを更新
        for area in expertise_areas:
            if area not in self.expertise_index:
                self.expertise_index[area] = set()
            self.expertise_index[area].add(expert_id)
        
        return profile
    
    def update_expertise_level(
        self,
        expert_id: str,
        expertise_area: str,
        level: ExpertLevel
    ) -> bool:
        """専門領域のレベルを更新"""
        if expert_id not in self.experts:
            return False
        
        expert = self.experts[expert_id]
        
        if expertise_area not in expert.expertise_areas:
            expert.expertise_areas.append(expertise_area)
        
        expert.expertise_levels[expertise_area] = level
        return True
    
    def get_expert(self, expert_id: str) -> Optional[ExpertProfile]:
        """専門家プロフィールを取得"""
        return self.experts.get(expert_id)
    
    def get_experts_by_expertise(
        self,
        expertise_area: str,
        min_level: Optional[ExpertLevel] = None
    ) -> List[ExpertProfile]:
        """専門領域別に専門家を取得"""
        if expertise_area not in self.expertise_index:
            return []
        
        experts = []
        for expert_id in self.expertise_index[expertise_area]:
            expert = self.experts[expert_id]
            
            # 最小レベルをチェック
            if min_level:
                current_level = expert.expertise_levels.get(expertise_area, ExpertLevel.JUNIOR)
                level_order = {
                    ExpertLevel.JUNIOR: 0,
                    ExpertLevel.INTERMEDIATE: 1,
                    ExpertLevel.SENIOR: 2,
                    ExpertLevel.PRINCIPAL: 3
                }
                if level_order[current_level] < level_order[min_level]:
                    continue
            
            # 可用性をチェック
            if expert.availability_status != AvailabilityStatus.AVAILABLE:
                continue
            
            # 容量をチェック
            if expert.current_active_reviews >= expert.max_concurrent_reviews:
                continue
            
            experts.append(expert)
        
        return experts
    
    def set_availability(
        self,
        expert_id: str,
        status: AvailabilityStatus,
        available_from: Optional[datetime] = None,
        available_until: Optional[datetime] = None
    ) -> bool:
        """可用性を設定"""
        if expert_id not in self.experts:
            return False
        
        expert = self.experts[expert_id]
        expert.availability_status = status
        expert.availability_from = available_from
        expert.availability_until = available_until
        
        return True
    
    def get_available_experts(self) -> List[ExpertProfile]:
        """利用可能な専門家を取得"""
        available = []
        for expert in self.experts.values():
            if expert.availability_status == AvailabilityStatus.AVAILABLE:
                if expert.current_active_reviews < expert.max_concurrent_reviews:
                    available.append(expert)
        
        return available
    
    def assign_review(
        self,
        expert_id: str,
        item_id: str,
        item_type: str,
        deadline: Optional[datetime] = None
    ) -> Optional[ReviewAssignment]:
        """レビューを割当"""
        
        if expert_id not in self.experts:
            return None
        
        expert = self.experts[expert_id]
        
        # 容量チェック
        if expert.current_active_reviews >= expert.max_concurrent_reviews:
            return None
        
        # 割当を作成
        assignment_id = str(uuid.uuid4())
        assignment = ReviewAssignment(
            assignment_id=assignment_id,
            expert_id=expert_id,
            item_id=item_id,
            item_type=item_type,
            deadline=deadline,
            status="pending"
        )
        
        self.assignments[assignment_id] = assignment
        expert.current_active_reviews += 1
        expert.last_active = datetime.utcnow()
        
        return assignment
    
    def complete_review(
        self,
        assignment_id: str,
        feedback: str,
        approved: bool = True
    ) -> bool:
        """レビューを完了"""
        
        if assignment_id not in self.assignments:
            return False
        
        assignment = self.assignments[assignment_id]
        expert = self.experts[assignment.expert_id]
        perf = self.performance[assignment.expert_id]
        
        assignment.completed_date = datetime.utcnow()
        assignment.status = "completed"
        assignment.feedback = feedback
        
        # 専門家の統計を更新
        expert.current_active_reviews -= 1
        expert.last_active = datetime.utcnow()
        
        perf.total_reviews += 1
        perf.completed_reviews += 1
        
        if approved:
            perf.approval_rate = perf.completed_reviews / perf.total_reviews
        
        # レビュー時間を計算
        review_time = (assignment.completed_date - assignment.assigned_date).total_seconds() / 3600
        perf.average_review_time_hours = (
            (perf.average_review_time_hours * (perf.total_reviews - 1) + review_time) /
            perf.total_reviews
        )
        
        return True
    
    def update_expert_performance(
        self,
        expert_id: str,
        accuracy: Optional[float] = None,
        reliability: Optional[float] = None,
        feedback: Optional[float] = None
    ) -> bool:
        """専門家のパフォーマンスを更新"""
        
        if expert_id not in self.performance:
            return False
        
        perf = self.performance[expert_id]
        
        if accuracy is not None:
            perf.accuracy_score = max(0.0, min(accuracy, 1.0))
        
        if reliability is not None:
            perf.reliability_score = max(0.0, min(reliability, 1.0))
        
        if feedback is not None:
            perf.feedback_score = max(0.0, min(feedback, 1.0))
        
        perf.last_performance_update = datetime.utcnow()
        
        return True
    
    def get_performance(self, expert_id: str) -> Optional[ExpertPerformance]:
        """専門家のパフォーマンスを取得"""
        return self.performance.get(expert_id)
    
    def get_expert_statistics(self) -> Dict:
        """専門家ネットワーク統計を取得"""
        
        if not self.experts:
            return {
                "total_experts": 0,
                "available_experts": 0,
                "expertise_areas": 0,
                "average_reviews": 0.0,
                "average_accuracy": 0.0
            }
        
        available_count = len(self.get_available_experts())
        
        total_reviews = sum(p.total_reviews for p in self.performance.values())
        avg_reviews = total_reviews / len(self.experts)
        
        avg_accuracy = sum(p.accuracy_score for p in self.performance.values()) / len(self.performance)
        
        return {
            "total_experts": len(self.experts),
            "available_experts": available_count,
            "expertise_areas": len(self.expertise_index),
            "average_reviews": avg_reviews,
            "average_accuracy": avg_accuracy,
            "total_reviews": total_reviews,
            "pending_assignments": len([a for a in self.assignments.values() if a.status == "pending"])
        }
    
    def get_top_performers(self, n: int = 10) -> List[Tuple[str, float]]:
        """パフォーマンスが高い専門家を取得"""
        
        # 複合スコアを計算
        scores = []
        for expert_id, perf in self.performance.items():
            composite_score = (
                perf.accuracy_score * 0.4 +
                perf.reliability_score * 0.4 +
                perf.feedback_score * 0.2
            )
            scores.append((self.experts[expert_id].name, composite_score))
        
        # 降順にソート
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:n]
    
    def generate_network_report(self) -> str:
        """ネットワークレポートを生成"""
        stats = self.get_expert_statistics()
        
        report = []
        report.append("=" * 60)
        report.append("EXPERT NETWORK REPORT")
        report.append(f"Generated: {datetime.utcnow().isoformat()}")
        report.append("=" * 60)
        report.append("")
        
        # 概要
        report.append("SUMMARY")
        report.append("-" * 60)
        report.append(f"Total Experts: {stats['total_experts']}")
        report.append(f"Available: {stats['available_experts']}")
        report.append(f"Expertise Areas: {stats['expertise_areas']}")
        report.append(f"Average Reviews: {stats['average_reviews']:.1f}")
        report.append(f"Average Accuracy: {stats['average_accuracy']:.2%}")
        report.append("")
        
        # 専門領域
        report.append("EXPERTISE AREAS")
        report.append("-" * 60)
        for area, expert_ids in sorted(self.expertise_index.items()):
            report.append(f"{area}: {len(expert_ids)} experts")
        report.append("")
        
        # トップパフォーマー
        report.append("TOP PERFORMERS")
        report.append("-" * 60)
        for i, (name, score) in enumerate(self.get_top_performers(5), 1):
            report.append(f"{i}. {name}: {score:.2%}")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
