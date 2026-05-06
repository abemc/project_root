"""
エージェント計画能力測定モジュール

エージェントの計画立案・実行能力を測定します：
- タスク分解能力
- 段階数の最適性
- リプランニング効率
- 不確実性への対応
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math


class PlanQuality(Enum):
    """計画品質の分類"""
    OPTIMAL = "optimal"                # 最適（段階が適切）
    GOOD = "good"                      # 良好
    ACCEPTABLE = "acceptable"          # 許容可能
    INEFFICIENT = "inefficient"        # 非効率
    FAILED = "failed"                  # 失敗


@dataclass
class PlanStep:
    """計画の単一ステップ"""
    step_number: int
    description: str
    estimated_duration: float          # 推定実行時間（秒）
    actual_duration: Optional[float] = None  # 実際の実行時間
    status: str = "pending"             # pending, executing, completed, failed
    success: bool = False               # 実行結果
    replan_required: bool = False       # リプランが必要だったか
    
    def get_efficiency(self) -> Optional[float]:
        """実行効率 (0-1, 推定<実際の場合は補正)"""
        if self.actual_duration is None:
            return None
        
        if self.estimated_duration == 0:
            return 0.5
        
        ratio = self.actual_duration / self.estimated_duration
        
        # 効率を計算（推定に近いほど高い）
        if ratio <= 1.0:
            efficiency = ratio  # 推定以内なら正確性に基づく
        else:
            # 推定超過時は逆数で計算
            efficiency = max(0.1, 1.0 / ratio)
        
        return min(1.0, efficiency)
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "step": self.step_number,
            "description": self.description,
            "estimated": self.estimated_duration,
            "actual": self.actual_duration,
            "status": self.status,
            "success": self.success,
            "efficiency": self.get_efficiency(),
        }


@dataclass
class ExecutionPlan:
    """完全な実行計画"""
    plan_id: str
    task_description: str
    steps: List[PlanStep] = field(default_factory=list)
    total_estimated_time: float = 0.0
    total_actual_time: Optional[float] = None
    replan_count: int = 0              # リプランの回数
    plan_quality: Optional[PlanQuality] = None
    success: bool = False
    constraints: List[str] = field(default_factory=list)  # 制約条件
    uncertain_factors: List[str] = field(default_factory=list)  # 不確実要因
    
    def add_step(self, step: PlanStep) -> None:
        """ステップを追加"""
        self.steps.append(step)
        self.total_estimated_time += step.estimated_duration
    
    def get_step_count_optimality(self) -> float:
        """ステップ数の最適性を評価 (0-1)"""
        if len(self.steps) == 0:
            return 0.0
        
        # 理想的なステップ数は sqrt(task_complexity) の関係にあると仮定
        # 複雑さをステップ数で推定
        task_complexity_estimate = len(self.steps) ** 2
        
        # 5-15ステップが最適と仮定
        if 5 <= len(self.steps) <= 15:
            return 0.9
        elif 3 <= len(self.steps) <= 20:
            return 0.7
        elif len(self.steps) == 1:
            return 0.3  # 過度に簡潔
        else:
            return 0.4  # 過度に複雑
    
    def get_execution_success_rate(self) -> float:
        """実行成功率 (0-1)"""
        if len(self.steps) == 0:
            return 0.0
        
        successful_steps = sum(1 for step in self.steps if step.success)
        return successful_steps / len(self.steps)
    
    def get_time_estimate_accuracy(self) -> Optional[float]:
        """時間推定精度 (0-1)"""
        if self.total_actual_time is None:
            return None
        
        if self.total_estimated_time == 0:
            return 0.5
        
        ratio = self.total_actual_time / self.total_estimated_time
        
        # 精度を計算（推定に近いほど高い）
        if ratio == 1.0:
            return 1.0
        elif 0.8 <= ratio <= 1.2:
            return 0.9
        elif 0.5 <= ratio <= 1.5:
            return 0.7
        elif 0.2 <= ratio <= 2.0:
            return 0.5
        else:
            return 0.2
    
    def get_adaptability_score(self) -> float:
        """適応性スコア (0-1: リプランニングの効率性)"""
        if len(self.steps) == 0:
            return 0.5
        
        # リプランなしが最適
        if self.replan_count == 0:
            return 0.95
        
        # リプラン回数ペナルティ
        replan_penalty = min(0.5, self.replan_count * 0.2)
        
        # 成功率によるボーナス
        success_bonus = self.get_execution_success_rate() * 0.3
        
        adaptability = max(0.2, 0.8 - replan_penalty + success_bonus)
        return min(1.0, adaptability)


class PlanningCapacityMeasurer:
    """計画能力測定エンジン"""
    
    def __init__(self):
        """初期化"""
        self.plans: List[ExecutionPlan] = []
    
    def create_plan(
        self,
        plan_id: str,
        task_description: str,
        constraints: List[str] = None,
        uncertain_factors: List[str] = None,
    ) -> ExecutionPlan:
        """新しい実行計画を作成"""
        plan = ExecutionPlan(
            plan_id=plan_id,
            task_description=task_description,
            constraints=constraints or [],
            uncertain_factors=uncertain_factors or [],
        )
        return plan
    
    def add_plan_step(
        self,
        plan: ExecutionPlan,
        description: str,
        estimated_duration: float,
    ) -> PlanStep:
        """計画にステップを追加"""
        step = PlanStep(
            step_number=len(plan.steps) + 1,
            description=description,
            estimated_duration=estimated_duration,
        )
        plan.add_step(step)
        return step
    
    def execute_step(
        self,
        step: PlanStep,
        actual_duration: float,
        success: bool = True,
    ) -> None:
        """ステップを実行"""
        step.status = "completed"
        step.actual_duration = actual_duration
        step.success = success
    
    def mark_replan_needed(self, plan: ExecutionPlan, step: PlanStep) -> None:
        """リプランが必要と判定"""
        step.replan_required = True
        plan.replan_count += 1
    
    def complete_plan(self, plan: ExecutionPlan, success: bool) -> None:
        """計画を完了"""
        plan.success = success
        
        # 実行時間を計算
        plan.total_actual_time = sum(
            step.actual_duration for step in plan.steps
            if step.actual_duration is not None
        )
        
        # 計画品質を評価
        plan.plan_quality = self._evaluate_plan_quality(plan)
        
        self.plans.append(plan)
    
    def _evaluate_plan_quality(self, plan: ExecutionPlan) -> PlanQuality:
        """計画品質を評価"""
        if not plan.success:
            return PlanQuality.FAILED
        
        # スコアに基づいて品質を判定
        scores = []
        
        # ステップ数最適性（40%）
        step_optimality = plan.get_step_count_optimality()
        scores.append(("step_optimality", step_optimality, 0.4))
        
        # 実行成功率（30%）
        success_rate = plan.get_execution_success_rate()
        scores.append(("success_rate", success_rate, 0.3))
        
        # 時間推定精度（20%）
        time_accuracy = plan.get_time_estimate_accuracy() or 0.5
        scores.append(("time_accuracy", time_accuracy, 0.2))
        
        # 適応性（10%）
        adaptability = plan.get_adaptability_score()
        scores.append(("adaptability", adaptability, 0.1))
        
        # 加重スコア計算
        weighted_score = sum(score * weight for _, score, weight in scores)
        
        # 品質判定
        if weighted_score >= 0.9:
            return PlanQuality.OPTIMAL
        elif weighted_score >= 0.75:
            return PlanQuality.GOOD
        elif weighted_score >= 0.60:
            return PlanQuality.ACCEPTABLE
        elif weighted_score >= 0.40:
            return PlanQuality.INEFFICIENT
        else:
            return PlanQuality.FAILED
    
    def get_planning_metrics(self) -> Dict:
        """計画に関するメトリクスを取得"""
        if not self.plans:
            return {}
        
        successful_plans = sum(1 for plan in self.plans if plan.success)
        
        # 計画品質の分布
        quality_distribution = {}
        for quality in PlanQuality:
            count = sum(
                1 for plan in self.plans
                if plan.plan_quality == quality
            )
            quality_distribution[quality.value] = count
        
        # ステップ数統計
        step_counts = [len(plan.steps) for plan in self.plans]
        
        # リプラン統計
        replan_counts = [plan.replan_count for plan in self.plans]
        
        return {
            "total_plans": len(self.plans),
            "success_rate": successful_plans / len(self.plans),
            "average_step_count": sum(step_counts) / len(step_counts),
            "average_replan_count": sum(replan_counts) / len(replan_counts),
            "quality_distribution": quality_distribution,
            "average_time_estimate_accuracy": self._average_metric(
                [plan.get_time_estimate_accuracy() for plan in self.plans]
            ),
            "average_adaptability": self._average_metric(
                [plan.get_adaptability_score() for plan in self.plans]
            ),
        }
    
    def _average_metric(self, values: List[Optional[float]]) -> Optional[float]:
        """オプション値のリストの平均を計算"""
        non_none_values = [v for v in values if v is not None]
        if not non_none_values:
            return None
        return sum(non_none_values) / len(non_none_values)
    
    def get_capacity_score(self) -> float:
        """全体的な計画能力スコア (0-1)"""
        if not self.plans:
            return 0.0
        
        metrics = self.get_planning_metrics()
        
        if not metrics:
            return 0.0
        
        # 複数要因の加重スコア
        weights = {
            "success_rate": 0.40,
            "average_adaptability": 0.30,
            "average_time_estimate_accuracy": 0.20,
            "step_optimality": 0.10,
        }
        
        score = 0.0
        
        # 成功率
        score += metrics["success_rate"] * weights["success_rate"]
        
        # 適応性
        if metrics["average_adaptability"] is not None:
            score += metrics["average_adaptability"] * weights["average_adaptability"]
        
        # 時間推定精度
        if metrics["average_time_estimate_accuracy"] is not None:
            score += metrics["average_time_estimate_accuracy"] * weights["average_time_estimate_accuracy"]
        
        # ステップ最適性（平均から推定）
        avg_steps = metrics["average_step_count"]
        step_optimality = self._estimate_step_optimality(avg_steps)
        score += step_optimality * weights["step_optimality"]
        
        return score
    
    def _estimate_step_optimality(self, avg_steps: float) -> float:
        """平均ステップ数から最適性を推定"""
        if 5 <= avg_steps <= 15:
            return 0.9
        elif 3 <= avg_steps <= 20:
            return 0.7
        else:
            return 0.4
    
    def export_plan_summary(self, plan: ExecutionPlan) -> Dict:
        """計画のサマリーをエクスポート"""
        return {
            "plan_id": plan.plan_id,
            "task_description": plan.task_description,
            "step_count": len(plan.steps),
            "success": plan.success,
            "quality": plan.plan_quality.value if plan.plan_quality else None,
            "estimated_time": plan.total_estimated_time,
            "actual_time": plan.total_actual_time,
            "replan_count": plan.replan_count,
            "step_optimality": plan.get_step_count_optimality(),
            "execution_success_rate": plan.get_execution_success_rate(),
            "time_estimate_accuracy": plan.get_time_estimate_accuracy(),
            "adaptability": plan.get_adaptability_score(),
            "steps": [step.to_dict() for step in plan.steps],
        }
    
    def reset_measurements(self):
        """測定をリセット"""
        self.plans = []
