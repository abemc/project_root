"""
エージェント意思決定フロー分析モジュール

エージェントの意思決定プロセスを追跡・分析し、
独立性、論理性、効率性を測定します。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import json
import csv
from collections import Counter
from pathlib import Path


class DecisionType(Enum):
    """意思決定の分類"""
    AUTONOMOUS = "autonomous"           # 完全自律
    GUIDED = "guided"                  # ガイド付き
    ESCALATED = "escalated"            # エスカレーション
    FALLBACK = "fallback"              # フォールバック


class DecisionQuality(Enum):
    """意思決定品質の分類"""
    OPTIMAL = "optimal"                # 最適
    GOOD = "good"                      # 良好
    ACCEPTABLE = "acceptable"          # 許容
    SUBOPTIMAL = "suboptimal"          # 準最適
    FAILED = "failed"                  # 失敗


@dataclass
class DecisionStep:
    """単一の意思決定ステップ"""
    step_id: int
    decision_type: DecisionType
    context: str                        # 決定コンテキスト
    options_considered: List[str] = field(default_factory=list)  # 検討した選択肢
    selected_option: str = ""           # 選択された選択肢
    reasoning: str = ""                 # 意思決定理由
    confidence: float = 0.0             # 信頼度 (0-1)
    quality: Optional[DecisionQuality] = None  # 後付けの品質評価
    timestamp: Optional[str] = None
    user_intervention: bool = False     # ユーザー介入が必要だったか
    
    def get_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "step_id": self.step_id,
            "decision_type": self.decision_type.value,
            "context": self.context,
            "options": self.options_considered,
            "selected": self.selected_option,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "quality": self.quality.value if self.quality else None,
            "intervention": self.user_intervention,
        }


@dataclass
class DecisionFlow:
    """一連の意思決定フロー（タスク実行全体）"""
    task_id: str
    task_description: str
    steps: List[DecisionStep] = field(default_factory=list)
    overall_success: bool = False
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    def add_step(self, step: DecisionStep) -> None:
        """ステップを追加"""
        if not step.timestamp:
            step.timestamp = datetime.now().isoformat()
        self.steps.append(step)
    
    def get_autonomy_score(self) -> float:
        """このフローの自律性スコア (0-1)"""
        if not self.steps:
            return 0.0
        
        autonomous_steps = sum(
            1 for step in self.steps
            if step.decision_type == DecisionType.AUTONOMOUS
        )
        return autonomous_steps / len(self.steps)
    
    def get_decision_quality_score(self) -> float:
        """意思決定品質スコア (0-1)"""
        if not self.steps:
            return 0.0
        
        quality_scores = {
            DecisionQuality.OPTIMAL: 1.0,
            DecisionQuality.GOOD: 0.85,
            DecisionQuality.ACCEPTABLE: 0.60,
            DecisionQuality.SUBOPTIMAL: 0.30,
            DecisionQuality.FAILED: 0.0,
        }
        
        total_score = 0.0
        rated_steps = 0
        
        for step in self.steps:
            if step.quality:
                total_score += quality_scores.get(step.quality, 0.0)
                rated_steps += 1
        
        if rated_steps == 0:
            return 0.5  # デフォルト
        
        return total_score / rated_steps
    
    def get_intervention_rate(self) -> float:
        """ユーザー介入率 (0-1)"""
        if not self.steps:
            return 0.0
        
        intervention_count = sum(
            1 for step in self.steps if step.user_intervention
        )
        return intervention_count / len(self.steps)
    
    def get_average_confidence(self) -> float:
        """平均信頼度 (0-1)"""
        if not self.steps:
            return 0.0
        
        confidences = [step.confidence for step in self.steps]
        return sum(confidences) / len(confidences)


class DecisionAnalyzer:
    """意思決定フロー分析エンジン"""
    
    def __init__(self):
        """初期化"""
        self.flows: List[DecisionFlow] = []
        self.analysis_cache: Dict = {}
    
    def create_flow(self, task_id: str, task_description: str) -> DecisionFlow:
        """新しい決定フローを作成"""
        flow = DecisionFlow(
            task_id=task_id,
            task_description=task_description,
            start_time=datetime.now().isoformat(),
        )
        return flow
    
    def record_decision(
        self,
        flow: DecisionFlow,
        decision_type: DecisionType,
        context: str,
        options: List[str],
        selected: str,
        reasoning: str,
        confidence: float,
        user_intervention: bool = False,
    ) -> DecisionStep:
        """決定ステップを記録"""
        step = DecisionStep(
            step_id=len(flow.steps) + 1,
            decision_type=decision_type,
            context=context,
            options_considered=options,
            selected_option=selected,
            reasoning=reasoning,
            confidence=confidence,
            user_intervention=user_intervention,
            timestamp=datetime.now().isoformat(),
        )
        flow.add_step(step)
        return step
    
    def evaluate_step_quality(
        self, step: DecisionStep, actual_outcome: bool, feedback: str = ""
    ) -> DecisionQuality:
        """ステップの意思決定品質を評価（後付け評価）"""
        # 決定タイプと実結果から品質を判定
        
        if step.decision_type == DecisionType.AUTONOMOUS:
            if actual_outcome:
                quality = DecisionQuality.OPTIMAL
            else:
                quality = DecisionQuality.SUBOPTIMAL
        
        elif step.decision_type == DecisionType.GUIDED:
            if actual_outcome:
                quality = DecisionQuality.GOOD
            else:
                quality = DecisionQuality.ACCEPTABLE
        
        elif step.decision_type == DecisionType.FALLBACK:
            if actual_outcome:
                quality = DecisionQuality.ACCEPTABLE
            else:
                quality = DecisionQuality.SUBOPTIMAL
        
        else:  # ESCALATED
            quality = DecisionQuality.GOOD
        
        # 信頼度との調整
        if step.confidence < 0.5 and actual_outcome:
            quality = DecisionQuality.GOOD  # 不確実性のある中での正解
        elif step.confidence > 0.8 and not actual_outcome:
            quality = DecisionQuality.FAILED  # 過信による失敗
        
        step.quality = quality
        return quality
    
    def complete_flow(
        self, flow: DecisionFlow, overall_success: bool
    ) -> DecisionFlow:
        """フロー完了時の処理"""
        flow.end_time = datetime.now().isoformat()
        flow.overall_success = overall_success
        self.flows.append(flow)
        return flow
    
    def analyze_decision_patterns(self) -> Dict:
        """全体の意思決定パターンを分析"""
        if not self.flows:
            return {}
        
        total_steps = sum(len(flow.steps) for flow in self.flows)
        
        if total_steps == 0:
            return {}
        
        # 決定タイプの分布
        decision_types_count = {}
        for flow in self.flows:
            for step in flow.steps:
                dt = step.decision_type.value
                decision_types_count[dt] = decision_types_count.get(dt, 0) + 1
        
        decision_types_dist = {
            k: v / total_steps for k, v in decision_types_count.items()
        }
        
        # 成功率
        successful_flows = sum(1 for flow in self.flows if flow.overall_success)
        success_rate = successful_flows / len(self.flows)
        
        # 平均自律性スコア
        autonomy_scores = [flow.get_autonomy_score() for flow in self.flows]
        avg_autonomy = sum(autonomy_scores) / len(autonomy_scores)
        
        # 平均品質スコア
        quality_scores = [flow.get_decision_quality_score() for flow in self.flows]
        avg_quality = sum(quality_scores) / len(quality_scores)
        
        # 平均介入率
        intervention_rates = [flow.get_intervention_rate() for flow in self.flows]
        avg_intervention = sum(intervention_rates) / len(intervention_rates)
        
        # 平均信頼度
        confidence_scores = [flow.get_average_confidence() for flow in self.flows]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        return {
            "total_flows": len(self.flows),
            "total_steps": total_steps,
            "decision_type_distribution": decision_types_dist,
            "success_rate": success_rate,
            "average_autonomy": avg_autonomy,
            "average_quality": avg_quality,
            "average_intervention_rate": avg_intervention,
            "average_confidence": avg_confidence,
        }
    
    def get_autonomy_metrics(self) -> Dict:
        """自律性に関するメトリクスを取得"""
        if not self.flows:
            return {}
        
        autonomy_scores = [flow.get_autonomy_score() for flow in self.flows]
        intervention_rates = [flow.get_intervention_rate() for flow in self.flows]
        
        return {
            "average_autonomy": sum(autonomy_scores) / len(autonomy_scores),
            "max_autonomy": max(autonomy_scores),
            "min_autonomy": min(autonomy_scores),
            "average_intervention_rate": sum(intervention_rates) / len(intervention_rates),
        }
    
    def get_decision_quality_metrics(self) -> Dict:
        """品質に関するメトリクスを取得"""
        if not self.flows:
            return {}
        
        quality_scores = [flow.get_decision_quality_score() for flow in self.flows]
        
        # 品質レベル別の集計
        quality_levels = {"optimal": 0, "good": 0, "acceptable": 0, "failed": 0}
        
        for flow in self.flows:
            for step in flow.steps:
                if step.quality:
                    if step.quality == DecisionQuality.OPTIMAL:
                        quality_levels["optimal"] += 1
                    elif step.quality == DecisionQuality.GOOD:
                        quality_levels["good"] += 1
                    elif step.quality == DecisionQuality.ACCEPTABLE:
                        quality_levels["acceptable"] += 1
                    elif step.quality == DecisionQuality.FAILED:
                        quality_levels["failed"] += 1
        
        total_rated = sum(quality_levels.values())
        
        return {
            "average_quality": sum(quality_scores) / len(quality_scores),
            "quality_distribution": {
                k: v / total_rated if total_rated > 0 else 0
                for k, v in quality_levels.items()
            },
        }
    
    def export_flow_summary(self, flow: DecisionFlow) -> Dict:
        """フローのサマリーをエクスポート"""
        return {
            "task_id": flow.task_id,
            "task_description": flow.task_description,
            "step_count": len(flow.steps),
            "success": flow.overall_success,
            "autonomy_score": flow.get_autonomy_score(),
            "quality_score": flow.get_decision_quality_score(),
            "intervention_rate": flow.get_intervention_rate(),
            "average_confidence": flow.get_average_confidence(),
            "steps": [step.get_dict() for step in flow.steps],
        }
    
    def reset_analysis(self):
        """分析データをリセット"""
        self.flows = []
        self.analysis_cache = {}
    
    def analyze_failure_patterns(self) -> Dict:
        """失敗パターンを分析"""
        failed_flows = [f for f in self.flows if not f.overall_success]
        
        if not failed_flows:
            return {
                "failure_rate": 0.0,
                "total_failures": 0,
                "patterns": {},
            }
        
        # 失敗率
        failure_rate = len(failed_flows) / len(self.flows)
        
        # 失敗時の決定タイプ分布
        failure_decision_types = []
        failed_quality_levels = []
        
        for flow in failed_flows:
            for step in flow.steps:
                failure_decision_types.append(step.decision_type.value)
                if step.quality:
                    failed_quality_levels.append(step.quality.value)
        
        # 失敗パターン検出
        patterns = {
            "decision_type_in_failures": dict(Counter(failure_decision_types)),
            "quality_in_failures": dict(Counter(failed_quality_levels)),
        }
        
        # 失敗に至る決定チェーン
        failure_chains = []
        for flow in failed_flows:
            chain = [
                f"{step.decision_type.value}({step.confidence:.2f})"
                for step in flow.steps
            ]
            failure_chains.append(" -> ".join(chain))
        
        patterns["failure_chains"] = failure_chains
        
        return {
            "failure_rate": failure_rate,
            "total_failures": len(failed_flows),
            "total_flows": len(self.flows),
            "patterns": patterns,
        }
    
    def analyze_decision_chains(self, max_chain_length: int = 10) -> Dict:
        """意思決定チェーンのパターンを分析"""
        chains = {}
        
        for flow in self.flows:
            # チェーンを生成
            chain_types = [step.decision_type.value for step in flow.steps]
            
            # 短いチェーンは省く
            if len(chain_types) < 2:
                continue
            
            # チェーンを正規化（最大長に制限）
            normalized_chain = " -> ".join(chain_types[:max_chain_length])
            
            if normalized_chain not in chains:
                chains[normalized_chain] = {
                    "count": 0,
                    "success_count": 0,
                    "avg_quality": 0.0,
                    "flows": [],
                }
            
            chains[normalized_chain]["count"] += 1
            if flow.overall_success:
                chains[normalized_chain]["success_count"] += 1
            
            chains[normalized_chain]["flows"].append(flow.task_id)
        
        # チェーンごとの統計
        for chain_key in chains:
            chain_info = chains[chain_key]
            chain_info["success_rate"] = (
                chain_info["success_count"] / chain_info["count"]
                if chain_info["count"] > 0
                else 0.0
            )
        
        return {
            "total_unique_chains": len(chains),
            "chains": chains,
        }
    
    def detect_risk_patterns(self) -> Dict:
        """リスクパターンを検出"""
        risks = {
            "high_confidence_failures": [],
            "excessive_escalations": [],
            "frequent_interventions": [],
            "inconsistent_chains": [],
        }
        
        for flow in self.flows:
            if not flow.overall_success:
                # 高い信頼度での失敗
                for step in flow.steps:
                    if step.confidence > 0.8 and step.quality == DecisionQuality.FAILED:
                        risks["high_confidence_failures"].append({
                            "task_id": flow.task_id,
                            "confidence": step.confidence,
                            "context": step.context,
                        })
            
            # 過度なエスカレーション
            escalation_count = sum(
                1 for step in flow.steps
                if step.decision_type == DecisionType.ESCALATED
            )
            if escalation_count > len(flow.steps) * 0.3:  # 30%以上
                risks["excessive_escalations"].append({
                    "task_id": flow.task_id,
                    "escalation_count": escalation_count,
                    "total_steps": len(flow.steps),
                })
            
            # 頻繁な介入
            intervention_count = sum(
                1 for step in flow.steps if step.user_intervention
            )
            if intervention_count > len(flow.steps) * 0.5:  # 50%以上
                risks["frequent_interventions"].append({
                    "task_id": flow.task_id,
                    "intervention_count": intervention_count,
                    "total_steps": len(flow.steps),
                })
        
        return risks
    
    def generate_autonomy_report(self) -> Dict:
        """エージェント自律性の総合レポート生成"""
        autonomy_metrics = self.get_autonomy_metrics()
        quality_metrics = self.get_decision_quality_metrics()
        pattern_analysis = self.analyze_decision_patterns()
        failure_analysis = self.analyze_failure_patterns()
        chain_analysis = self.analyze_decision_chains()
        risk_patterns = self.detect_risk_patterns()
        
        # 自律性スコア（統合指標）
        autonomy_score = (
            autonomy_metrics.get("average_autonomy", 0) * 0.4 +
            (1 - autonomy_metrics.get("average_intervention_rate", 0)) * 0.3 +
            quality_metrics.get("average_quality", 0) * 0.3
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "autonomy_score": autonomy_score,
            "autonomy_metrics": autonomy_metrics,
            "quality_metrics": quality_metrics,
            "pattern_analysis": pattern_analysis,
            "failure_analysis": failure_analysis,
            "chain_analysis": chain_analysis,
            "risk_patterns": risk_patterns,
            "summary": {
                "total_tasks": len(self.flows),
                "overall_success_rate": pattern_analysis.get("success_rate", 0),
                "average_autonomy": autonomy_metrics.get("average_autonomy", 0),
                "average_quality": quality_metrics.get("average_quality", 0),
                "intervention_rate": autonomy_metrics.get("average_intervention_rate", 0),
                "failure_rate": failure_analysis.get("failure_rate", 0),
            },
        }
    
    def export_to_json(self, filepath: Path) -> None:
        """分析結果をJSONにエクスポート"""
        report = self.generate_autonomy_report()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def export_flows_to_csv(self, filepath: Path) -> None:
        """フロー情報をCSVにエクスポート"""
        if not self.flows:
            return
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "task_id",
                    "task_description",
                    "success",
                    "autonomy_score",
                    "quality_score",
                    "intervention_rate",
                    "average_confidence",
                    "step_count",
                ],
            )
            writer.writeheader()
            
            for flow in self.flows:
                writer.writerow({
                    "task_id": flow.task_id,
                    "task_description": flow.task_description,
                    "success": flow.overall_success,
                    "autonomy_score": flow.get_autonomy_score(),
                    "quality_score": flow.get_decision_quality_score(),
                    "intervention_rate": flow.get_intervention_rate(),
                    "average_confidence": flow.get_average_confidence(),
                    "step_count": len(flow.steps),
                })
    
    def export_steps_to_csv(self, filepath: Path) -> None:
        """ステップ詳細をCSVにエクスポート"""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "task_id",
                    "step_id",
                    "decision_type",
                    "context",
                    "selected_option",
                    "confidence",
                    "quality",
                    "intervention",
                    "timestamp",
                ],
            )
            writer.writeheader()
            
            for flow in self.flows:
                for step in flow.steps:
                    writer.writerow({
                        "task_id": flow.task_id,
                        "step_id": step.step_id,
                        "decision_type": step.decision_type.value,
                        "context": step.context,
                        "selected_option": step.selected_option,
                        "confidence": step.confidence,
                        "quality": step.quality.value if step.quality else "",
                        "intervention": step.user_intervention,
                        "timestamp": step.timestamp,
                    })
    
    def print_summary(self) -> None:
        """サマリーをコンソールに出力"""
        report = self.generate_autonomy_report()
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("エージェント自律性分析レポート")
        print("="*60)
        print(f"タイムスタンプ: {report['timestamp']}")
        print("\n【総合指標】")
        print(f"  自律性スコア: {report['autonomy_score']:.2%}")
        print("\n【タスク統計】")
        print(f"  処理タスク数: {summary['total_tasks']}")
        print(f"  成功率: {summary['overall_success_rate']:.2%}")
        print("\n【自律性指標】")
        print(f"  平均自律性: {summary['average_autonomy']:.2%}")
        print(f"  ユーザー介入率: {summary['intervention_rate']:.2%}")
        print("\n【品質指標】")
        print(f"  平均品質スコア: {summary['average_quality']:.2%}")
        print(f"  失敗率: {summary['failure_rate']:.2%}")
        print("="*60 + "\n")
