"""
Value Conflict Resolver: 複数価値の衝突解決

プライバシー vs 有用性、安全性 vs 効率性など
複数の価値が衝突する場合に、ユーザーポリシーに基づいて解決。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Value(Enum):
    """エージェントの基本価値"""
    PRIVACY = "privacy"  # プライバシー保護
    UTILITY = "utility"  # 利用可能性・有用性
    SAFETY = "safety"  # 安全性
    EFFICIENCY = "efficiency"  # 効率性
    TRANSPARENCY = "transparency"  # 透明性
    AUTONOMY = "autonomy"  # 自律性
    FAIRNESS = "fairness"  # 公平性
    ACCOUNTABILITY = "accountability"  # 説明責任


@dataclass
class ValuePriority:
    """価値の優先度設定"""
    value: Value
    weight: float  # 重要度 (0-1)
    threshold: float  # 最小満足度 (0-1)
    override_allowed: bool  # オーバーライド許可


@dataclass
class ConflictScenario:
    """値の衝突シナリオ"""
    scenario_id: str
    conflicting_values: List[Value]  # 衝突する価値
    action_proposed: str  # 提案アクション
    impact_analysis: Dict[Value, float]  # 各価値への影響 (-1〜1)
    user_policy: Optional[Dict[Value, float]] = None  # ユーザーポリシー
    resolved_decision: Optional[str] = None  # 解決決定
    resolution_timestamp: Optional[datetime] = None


class ValueConflictResolver:
    """複数価値衝突解決"""
    
    def __init__(self):
        """初期化"""
        self.user_policies: Dict[Value, ValuePriority] = {}
        self.conflict_history: List[ConflictScenario] = []
        self.resolution_rules: List[Callable] = []
        self._init_default_policies()
    
    def _init_default_policies(self):
        """デフォルトユーザーポリシーを初期化"""
        # 標準的なバランス型ポリシー
        default_weights = {
            Value.SAFETY: ValuePriority(Value.SAFETY, 1.0, 0.9, False),
            Value.PRIVACY: ValuePriority(Value.PRIVACY, 0.9, 0.7, True),
            Value.ACCOUNTABILITY: ValuePriority(Value.ACCOUNTABILITY, 0.85, 0.8, False),
            Value.FAIRNESS: ValuePriority(Value.FAIRNESS, 0.8, 0.7, True),
            Value.TRANSPARENCY: ValuePriority(Value.TRANSPARENCY, 0.75, 0.6, True),
            Value.UTILITY: ValuePriority(Value.UTILITY, 0.7, 0.5, True),
            Value.EFFICIENCY: ValuePriority(Value.EFFICIENCY, 0.6, 0.4, True),
            Value.AUTONOMY: ValuePriority(Value.AUTONOMY, 0.5, 0.3, True),
        }
        
        self.user_policies = default_weights
        logger.info("Default value priorities initialized")
    
    def set_user_policy(self, policies: Dict[Value, ValuePriority]):
        """ユーザーポリシーを設定"""
        self.user_policies = policies
        logger.info("User policies updated")
    
    def resolve_conflict(
        self,
        action_proposed: str,
        conflicting_values: List[Value],
        impact_analysis: Dict[Value, float],
    ) -> Tuple[str, float, Dict[str, any]]:
        """
        価値衝突を解決
        
        Args:
            action_proposed: 提案アクション
            conflicting_values: 衝突する価値のリスト
            impact_analysis: 各価値への影響 (-1〜1)
        
        Returns:
            (解決決定, 総合スコア, 詳細情報)
        """
        scenario = ConflictScenario(
            scenario_id=f"conflict_{datetime.now().timestamp()}",
            conflicting_values=conflicting_values,
            action_proposed=action_proposed,
            impact_analysis=impact_analysis,
            user_policy=self.user_policies.copy(),
        )
        
        # 1. 各価値の満足度を計算
        satisfaction_scores = self._calculate_satisfaction(
            impact_analysis,
            self.user_policies,
        )
        
        # 2. ポリシー違反をチェック
        violations = self._check_policy_violations(satisfaction_scores)
        
        # 3. 衝突を分析
        conflict_analysis = self._analyze_conflict(
            conflicting_values,
            satisfaction_scores,
        )
        
        # 4. 解決戦略を選択
        decision, total_score, strategy = self._choose_resolution(
            action_proposed,
            satisfaction_scores,
            violations,
            conflict_analysis,
        )
        
        # 結果を記録
        scenario.resolved_decision = decision
        scenario.resolution_timestamp = datetime.now()
        self.conflict_history.append(scenario)
        
        logger.info(f"Conflict resolved: {decision} (score: {total_score:.2f})")
        
        return decision, total_score, {
            'satisfaction_scores': satisfaction_scores,
            'violations': violations,
            'conflict_analysis': conflict_analysis,
            'strategy_used': strategy,
        }
    
    def _calculate_satisfaction(
        self,
        impact_analysis: Dict[Value, float],
        policies: Dict[Value, ValuePriority],
    ) -> Dict[Value, float]:
        """各価値の満足度を計算"""
        satisfaction = {}
        
        for value, priority in policies.items():
            impact = impact_analysis.get(value, 0.0)
            
            # impact: -1〜1 を満足度 0〜1 に変換
            # 負の影響は許容範囲内か判定
            if impact >= 0:
                satisfaction[value] = impact
            else:
                # 負の影響の許容度をしきい値で判定
                tolerance = 1.0 - priority.threshold
                if abs(impact) <= tolerance:
                    satisfaction[value] = max(0, 1.0 + impact)
                else:
                    satisfaction[value] = 0.0  # 違反
        
        return satisfaction
    
    def _check_policy_violations(
        self,
        satisfaction_scores: Dict[Value, float],
    ) -> List[Tuple[Value, float]]:
        """ポリシー違反をチェック"""
        violations = []
        
        for value, satisfaction in satisfaction_scores.items():
            priority = self.user_policies.get(value)
            if priority and satisfaction < priority.threshold:
                deficit = priority.threshold - satisfaction
                violations.append((value, deficit))
        
        return violations
    
    def _analyze_conflict(
        self,
        conflicting_values: List[Value],
        satisfaction_scores: Dict[Value, float],
    ) -> Dict[str, any]:
        """衝突を分析"""
        analysis = {
            'conflict_pairs': [],
            'most_affected_value': None,
            'least_affected_value': None,
            'severity': 0.0,
        }
        
        # 衝突するペアを特定
        for i, v1 in enumerate(conflicting_values):
            for v2 in conflicting_values[i+1:]:
                score_diff = abs(
                    satisfaction_scores.get(v1, 0.5) -
                    satisfaction_scores.get(v2, 0.5)
                )
                analysis['conflict_pairs'].append({
                    'values': (v1, v2),
                    'difference': score_diff,
                })
        
        # 最も影響を受ける価値
        if satisfaction_scores:
            most = min(satisfaction_scores.items(), key=lambda x: x[1])
            least = max(satisfaction_scores.items(), key=lambda x: x[1])
            analysis['most_affected_value'] = most[0]
            analysis['least_affected_value'] = least[0]
            analysis['severity'] = (most[1] - least[1])
        
        return analysis
    
    def _choose_resolution(
        self,
        action_proposed: str,
        satisfaction_scores: Dict[Value, float],
        violations: List[Tuple[Value, float]],
        conflict_analysis: Dict,
    ) -> Tuple[str, float, str]:
        """解決戦略を選択"""
        
        # 総合スコアを計算
        weights = {
            v: p.weight for v, p in self.user_policies.items()
        }
        total_score = sum(
            satisfaction_scores.get(v, 0.0) * weight
            for v, weight in weights.items()
        ) / sum(weights.values())
        
        # 違反がない場合
        if not violations:
            return (
                f"APPROVE: {action_proposed}",
                total_score,
                "all_values_satisfied",
            )
        
        # 違反がある場合
        if len(violations) == 1:
            violated_value, deficit = violations[0]
            
            # オーバーライド許可をチェック
            if self.user_policies[violated_value].override_allowed and deficit < 0.15:
                return (
                    f"APPROVE_WITH_MITIGATION: {action_proposed} "
                    f"(Monitor {violated_value.value})",
                    total_score,
                    "single_violation_overridable",
                )
            else:
                return (
                    f"REJECT: {action_proposed} (violates {violated_value.value})",
                    total_score,
                    "single_critical_violation",
                )
        
        # 複数違反の場合
        return (
            f"REJECT: {action_proposed} (violates multiple values: "
            f"{', '.join(v.value for v, _ in violations)})",
            total_score,
            "multiple_violations",
        )
    
    def suggest_alternative_action(
        self,
        original_action: str,
        violations: List[Tuple[Value, float]],
        context: Dict[str, any],
    ) -> Optional[str]:
        """
        違反を回避する代替アクションを提案
        
        Args:
            original_action: 元のアクション
            violations: ポリシー違反
            context: コンテキスト
        
        Returns:
            代替アクション
        """
        if not violations:
            return None
        
        most_critical_value = violations[0][0]
        
        alternatives = {
            Value.PRIVACY: "Add privacy-preserving processing (e.g., anonymization, differential privacy)",
            Value.SAFETY: "Add safety validation step before execution",
            Value.TRANSPARENCY: "Generate detailed explanation of the action",
            Value.ACCOUNTABILITY: "Log action for audit trail and add human review checkpoint",
            Value.FAIRNESS: "Add fairness check to ensure equitable treatment",
            Value.UTILITY: "Modify action to improve usefulness without sacrificing other values",
            Value.EFFICIENCY: "Optimize execution path to maintain efficiency",
            Value.AUTONOMY: "Request user input for decision-making",
        }
        
        alternative = alternatives.get(most_critical_value, None)
        
        if alternative:
            return f"Alternative: {alternative}"
        
        return None
    
    def explain_resolution(
        self,
        scenario_id: str,
    ) -> Optional[str]:
        """
        解決過程を説明
        
        Args:
            scenario_id: シナリオID
        
        Returns:
            説明文
        """
        # シナリオを検索
        scenario = None
        for s in self.conflict_history:
            if s.scenario_id == scenario_id:
                scenario = s
                break
        
        if not scenario:
            return None
        
        explanation = f"""
Conflict Resolution Report
──────────────────────────
Scenario: {scenario_id}
Action Proposed: {scenario.action_proposed}

Conflicting Values:
{chr(10).join(f'  - {v.value}' for v in scenario.conflicting_values)}

Impact Analysis:
{chr(10).join(f'  {v.value}: {scenario.impact_analysis.get(v, 0):+.2f}' for v in scenario.conflicting_values)}

Resolution Decision:
{scenario.resolved_decision}

Timestamp: {scenario.resolution_timestamp}
        """.strip()
        
        return explanation
    
    def get_conflict_statistics(self) -> Dict[str, any]:
        """衝突統計を取得"""
        if not self.conflict_history:
            return {'total_conflicts': 0}
        
        approved = len([
            s for s in self.conflict_history
            if s.resolved_decision and 'APPROVE' in s.resolved_decision
        ])
        rejected = len([
            s for s in self.conflict_history
            if s.resolved_decision and 'REJECT' in s.resolved_decision
        ])
        
        value_violations = {}
        for scenario in self.conflict_history:
            for value in scenario.conflicting_values:
                value_violations[value.value] = value_violations.get(value.value, 0) + 1
        
        return {
            'total_conflicts': len(self.conflict_history),
            'approved': approved,
            'rejected': rejected,
            'approval_rate': approved / len(self.conflict_history) if self.conflict_history else 0,
            'most_conflicted_value': max(value_violations, key=value_violations.get) if value_violations else None,
        }
