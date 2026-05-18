"""
Decision Explainer: 推論プロセスの可視化・説明

AIが「なぜこのツールを選んだか」「なぜこのパラメータを使ったか」を
自然言語で説明し、透明性と信頼性を確保。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExplanationType(Enum):
    """説明の種別"""
    TOOL_SELECTION = "tool_selection"  # ツール選択理由
    PARAMETER_CHOICE = "parameter_choice"  # パラメータ選択理由
    STRATEGY_RATIONALE = "strategy_rationale"  # 戦略の根拠
    REJECTION_REASON = "rejection_reason"  # 却下理由
    CONFIDENCE_SCORE = "confidence_score"  # 信頼度説明


@dataclass
class ExplanationItem:
    """説明アイテム"""
    explanation_type: ExplanationType
    content: str  # 説明文
    reasoning_chain: List[str]  # 推論ステップ
    evidence: List[Dict[str, Any]]  # 根拠データ
    confidence: float  # 説明の確信度 (0-1)
    alternatives: Optional[List[str]] = None  # 他の選択肢
    timestamp: datetime = None


class DecisionExplainer:
    """意思決定説明管理"""
    
    def __init__(self):
        """初期化"""
        self.explanations: List[ExplanationItem] = []
        
        # 説明テンプレート
        self.templates = {
            'tool_selection_high_conf': (
                "Selecting {tool_name} because: "
                "This task requires {capability}. "
                "{tool_name} has the highest success rate ({success_rate:.1%}) "
                "for this type of task. "
                "Historical data shows {previous_uses} previous successful uses."
            ),
            'tool_selection_medium_conf': (
                "Selecting {tool_name} with moderate confidence: "
                "This task matches {task_type}. "
                "Several tools could work, but {tool_name} "
                "is a reasonable choice ({confidence:.1%} confidence). "
                "Alternative options: {alternatives}."
            ),
            'tool_selection_low_conf': (
                "Selecting {tool_name} with low confidence: "
                "The task is ambiguous. {tool_name} is selected as a fallback option. "
                "Recommend human review if results are unexpected. "
                "Better alternatives might be: {alternatives}."
            ),
            'parameter_selection': (
                "Setting {param_name}={param_value}: "
                "Based on {context_info}. "
                "Success rate with this value: {success_rate:.1%}. "
                "Range: {min_val} to {max_val}."
            ),
            'strategy_rationale': (
                "Choosing {strategy_name} strategy: "
                "Task characteristics: {task_characteristics}. "
                "This strategy is optimal for: {optimal_for}. "
                "Expected benefits: {benefits}. "
                "Potential risks: {risks}."
            ),
        }
    
    def explain_tool_selection(
        self,
        task_description: str,
        selected_tool: str,
        tool_candidates: List[str],
        success_rates: Dict[str, float],
        confidence: float,
        historical_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        ツール選択を説明
        
        Args:
            task_description: タスク説明
            selected_tool: 選択されたツール
            tool_candidates: 候補ツール
            success_rates: ツール毎の成功率
            confidence: 選択信頼度
            historical_data: 履歴データ
        
        Returns:
            説明文
        """
        selected_success_rate = success_rates.get(selected_tool, 0.0)
        
        # 信頼度に基づいてテンプレートを選択
        if confidence >= 0.8:
            template_key = 'tool_selection_high_conf'
            alternatives_str = "None - clear winner"
            reasoning = f"Task '{task_description}' matches {selected_tool}'s primary use case"
        elif confidence >= 0.5:
            template_key = 'tool_selection_medium_conf'
            alternative_tools = [t for t in tool_candidates if t != selected_tool]
            alternatives_str = ", ".join(alternative_tools[:2])
            reasoning = f"Task characteristics align with {selected_tool}"
        else:
            template_key = 'tool_selection_low_conf'
            alternative_tools = [t for t in tool_candidates if t != selected_tool]
            alternatives_str = ", ".join(alternative_tools[:2])
            reasoning = f"Ambiguous task, {selected_tool} is reasonable fallback"
        
        explanation_text = self.templates[template_key].format(
            tool_name=selected_tool,
            capability=self._infer_capability(selected_tool),
            success_rate=selected_success_rate,
            previous_uses=historical_data.get('previous_uses', 0) if historical_data else 0,
            task_type=self._classify_task(task_description),
            confidence=confidence,
            alternatives=alternatives_str,
        )
        
        # 説明をログに記録
        explanation = ExplanationItem(
            explanation_type=ExplanationType.TOOL_SELECTION,
            content=explanation_text,
            reasoning_chain=[
                f"Analyze task: {task_description}",
                f"Identify required capability: {self._infer_capability(selected_tool)}",
                f"Evaluate {len(tool_candidates)} candidate tools",
                f"Compare success rates: {success_rates}",
                f"Select {selected_tool} (confidence: {confidence:.1%})",
            ],
            evidence=[
                {'type': 'success_rate', 'tool': selected_tool, 'rate': selected_success_rate},
                {'type': 'candidate_count', 'count': len(tool_candidates)},
                {'type': 'confidence_score', 'score': confidence},
            ],
            confidence=confidence,
            alternatives=tool_candidates,
            timestamp=datetime.now(),
        )
        
        self.explanations.append(explanation)
        logger.info(f"Tool selection explained: {selected_tool}")
        
        return explanation_text
    
    def explain_parameter_selection(
        self,
        tool_name: str,
        parameter_name: str,
        parameter_value: Any,
        context: Dict[str, Any],
        success_metric: Optional[float] = None,
    ) -> str:
        """
        パラメータ選択を説明
        
        Args:
            tool_name: ツール名
            parameter_name: パラメータ名
            parameter_value: 選択値
            context: コンテキスト情報
            success_metric: 成功メトリクス
        
        Returns:
            説明文
        """
        explanation_text = self.templates['parameter_selection'].format(
            param_name=parameter_name,
            param_value=parameter_value,
            context_info=self._format_context(context),
            success_rate=success_metric or 0.75,
            min_val=context.get('min_value', 'N/A'),
            max_val=context.get('max_value', 'N/A'),
        )
        
        explanation = ExplanationItem(
            explanation_type=ExplanationType.PARAMETER_CHOICE,
            content=explanation_text,
            reasoning_chain=[
                f"Tool: {tool_name}",
                f"Parameter: {parameter_name}",
                f"Context: {context.get('scenario', 'standard')}",
                f"Applying heuristic: {context.get('heuristic', 'default')}",
                f"Selected value: {parameter_value}",
            ],
            evidence=[
                {'type': 'context', 'context': context},
                {'type': 'success_metric', 'metric': success_metric},
            ],
            confidence=context.get('confidence', 0.7),
            timestamp=datetime.now(),
        )
        
        self.explanations.append(explanation)
        logger.info(f"Parameter selection explained: {tool_name}.{parameter_name}={parameter_value}")
        
        return explanation_text
    
    def explain_strategy(
        self,
        strategy_name: str,
        task_characteristics: List[str],
        rationale: Dict[str, Any],
    ) -> str:
        """
        戦略選択を説明
        
        Args:
            strategy_name: 戦略名
            task_characteristics: タスク特性リスト
            rationale: 根拠情報
        
        Returns:
            説明文
        """
        explanation_text = self.templates['strategy_rationale'].format(
            strategy_name=strategy_name,
            task_characteristics=", ".join(task_characteristics),
            optimal_for=rationale.get('optimal_for', 'standard tasks'),
            benefits=", ".join(rationale.get('benefits', ['Efficient', 'Scalable'])),
            risks=", ".join(rationale.get('risks', ['None identified'])),
        )
        
        explanation = ExplanationItem(
            explanation_type=ExplanationType.STRATEGY_RATIONALE,
            content=explanation_text,
            reasoning_chain=[
                f"Task characteristics: {task_characteristics}",
                f"Evaluate strategies: {rationale.get('considered_strategies', [])}",
                f"Compare performance metrics",
                f"Select optimal strategy: {strategy_name}",
            ],
            evidence=[
                {'type': 'characteristics', 'items': task_characteristics},
                {'type': 'rationale', 'details': rationale},
            ],
            confidence=rationale.get('confidence', 0.8),
            alternatives=rationale.get('considered_strategies', []),
            timestamp=datetime.now(),
        )
        
        self.explanations.append(explanation)
        logger.info(f"Strategy explanation: {strategy_name}")
        
        return explanation_text
    
    def explain_rejection(
        self,
        tool_name: str,
        reason: str,
        alternatives: List[str],
    ) -> str:
        """
        ツール却下理由を説明
        
        Args:
            tool_name: ツール名
            reason: 却下理由
            alternatives: 代替案
        
        Returns:
            説明文
        """
        explanation_text = (
            f"{tool_name} was not selected because: {reason}. "
            f"Instead, considering: {', '.join(alternatives)}. "
            f"This tool may be reconsidered if conditions change."
        )
        
        explanation = ExplanationItem(
            explanation_type=ExplanationType.REJECTION_REASON,
            content=explanation_text,
            reasoning_chain=[
                f"Evaluate tool: {tool_name}",
                f"Check against criteria",
                f"Identify blocker: {reason}",
                f"Reject and consider alternatives",
            ],
            evidence=[
                {'type': 'rejection_reason', 'reason': reason},
                {'type': 'alternatives', 'tools': alternatives},
            ],
            confidence=0.9,
            alternatives=alternatives,
            timestamp=datetime.now(),
        )
        
        self.explanations.append(explanation)
        logger.info(f"Tool rejection explained: {tool_name}")
        
        return explanation_text
    
    def explain_confidence(
        self,
        decision_item: str,
        confidence_score: float,
        factors: List[Dict[str, Any]],
    ) -> str:
        """
        信頼度スコアを説明
        
        Args:
            decision_item: 意思決定対象
            confidence_score: 信頼度スコア (0-1)
            factors: スコア計算要因
        
        Returns:
            説明文
        """
        factor_descriptions = [
            f"{f.get('name', 'Unknown')}: {f.get('contribution', 0):.1%}" 
            for f in factors
        ]
        
        explanation_text = (
            f"Confidence in {decision_item}: {confidence_score:.1%}. "
            f"Contributing factors: {', '.join(factor_descriptions)}. "
        )
        
        if confidence_score >= 0.8:
            explanation_text += "High confidence - decision is reliable."
        elif confidence_score >= 0.5:
            explanation_text += "Medium confidence - human review recommended."
        else:
            explanation_text += "Low confidence - human intervention recommended."
        
        explanation = ExplanationItem(
            explanation_type=ExplanationType.CONFIDENCE_SCORE,
            content=explanation_text,
            reasoning_chain=[
                f"Evaluate decision: {decision_item}",
                f"Calculate confidence from factors: {[f.get('name') for f in factors]}",
                f"Final score: {confidence_score:.1%}",
            ],
            evidence=factors,
            confidence=0.95,  # 説明自体の確実性
            timestamp=datetime.now(),
        )
        
        self.explanations.append(explanation)
        logger.info(f"Confidence explained: {decision_item} ({confidence_score:.1%})")
        
        return explanation_text
    
    def _infer_capability(self, tool_name: str) -> str:
        """ツール名から推定される機能を取得"""
        capabilities = {
            'web_search': 'information retrieval from the internet',
            'database_query': 'structured data querying and analysis',
            'file_create': 'file creation and data persistence',
            'file_modify': 'file editing and content updates',
            'api_call': 'external API communication',
            'code_execution': 'computational tasks and algorithms',
        }
        return capabilities.get(tool_name, f'{tool_name} functionality')
    
    def _classify_task(self, task_description: str) -> str:
        """タスク説明から分類を推定"""
        task_lower = task_description.lower()
        
        if any(word in task_lower for word in ['search', 'find', 'query', 'look up']):
            return 'information_retrieval'
        elif any(word in task_lower for word in ['create', 'write', 'generate']):
            return 'content_generation'
        elif any(word in task_lower for word in ['modify', 'edit', 'update']):
            return 'content_modification'
        elif any(word in task_lower for word in ['delete', 'remove']):
            return 'content_deletion'
        else:
            return 'general'
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """コンテキスト情報をフォーマット"""
        parts = []
        for key, value in context.items():
            if key != 'confidence':
                parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "standard context"
    
    def get_explanation(self, index: int = -1) -> Optional[ExplanationItem]:
        """説明を取得"""
        if not self.explanations:
            return None
        return self.explanations[index]
    
    def get_all_explanations(self) -> List[ExplanationItem]:
        """すべての説明を取得"""
        return self.explanations.copy()
    
    def get_explanations_by_type(
        self,
        explanation_type: ExplanationType,
    ) -> List[ExplanationItem]:
        """種別別の説明を取得"""
        return [e for e in self.explanations if e.explanation_type == explanation_type]
    
    def clear_history(self):
        """説明履歴をクリア"""
        self.explanations = []
        logger.info("Explanation history cleared")
    
    def export_explanation_report(self) -> Dict[str, Any]:
        """説明レポートをエクスポート"""
        return {
            'total_explanations': len(self.explanations),
            'by_type': {
                exp_type.value: len(self.get_explanations_by_type(exp_type))
                for exp_type in ExplanationType
            },
            'avg_confidence': (
                sum(e.confidence for e in self.explanations) / len(self.explanations)
                if self.explanations else 0.0
            ),
            'recent_explanations': [
                {
                    'type': e.explanation_type.value,
                    'content': e.content[:100],  # 最初の100文字
                    'confidence': e.confidence,
                    'timestamp': e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in self.explanations[-10:]  # 最新10件
            ],
        }
