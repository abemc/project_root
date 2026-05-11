"""
Phase 7: 知識統合・推論レイヤー

複数ドメイン知識を統合・推論するコンポーネント群
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ============================================================
# データクラス定義
# ============================================================

@dataclass
class IntegratedKnowledge:
    """統合知識"""
    primary_domain: str                    # 主要ドメイン
    relevant_domains: List[str] = field(default_factory=list)  # 関連ドメイン
    integrated_facts: List[Dict] = field(default_factory=list)  # 統合事実
    contradictions: List[Dict] = field(default_factory=list)   # 矛盾
    synthesis: str = ""                    # 統合的説明


@dataclass
class CausalRelation:
    """因果関係"""
    cause: str                             # 原因
    effect: str                            # 結果
    strength: float = 0.7                  # 因果強度
    temporal_lag: Optional[str] = None     # 時間的ラグ
    conditions: List[str] = field(default_factory=list)  # 条件
    confidence: float = 0.8                # 信頼度


@dataclass
class Uncertainty:
    """不確実性"""
    level: float                           # 不確実性レベル(0-1)
    sources: List[str] = field(default_factory=list)  # 不確実性の源
    confidence_interval: Tuple[float, float] = (0.0, 1.0)  # 信頼区間
    alternative_interpretations: List[str] = field(default_factory=list)  # 代替解釈


# ============================================================
# KnowledgeIntegrator: マルチドメイン知識統合
# ============================================================

class KnowledgeIntegrator:
    """複数ドメイン知識を統合"""
    
    def __init__(self):
        logger.info("KnowledgeIntegrator initialized")
    
    def integrate_knowledge(self, primary_domain: str, related_domains: List[str],
                           query: str) -> IntegratedKnowledge:
        """知識を統合"""
        integrated_facts = self._gather_facts(primary_domain, related_domains, query)
        contradictions = self._detect_domain_contradictions(
            primary_domain, related_domains, query
        )
        synthesis = self._synthesize_knowledge(
            primary_domain, integrated_facts, contradictions
        )
        
        return IntegratedKnowledge(
            primary_domain=primary_domain,
            relevant_domains=related_domains,
            integrated_facts=integrated_facts,
            contradictions=contradictions,
            synthesis=synthesis,
        )
    
    def _gather_facts(self, primary_domain: str, related_domains: List[str],
                     query: str) -> List[Dict]:
        """複数ドメインから事実を収集"""
        facts = []
        
        # 主要ドメインの事実
        facts.append({
            'domain': primary_domain,
            'type': 'primary',
            'relevance': 1.0,
            'fact': f'Primary knowledge about {query} from {primary_domain}',
        })
        
        # 関連ドメインの事実
        for domain in related_domains:
            facts.append({
                'domain': domain,
                'type': 'supporting',
                'relevance': 0.7,
                'fact': f'Related knowledge from {domain} domain',
            })
        
        return facts
    
    def _detect_domain_contradictions(self, primary_domain: str, 
                                     related_domains: List[str],
                                     query: str) -> List[Dict]:
        """ドメイン間の矛盾を検出"""
        contradictions = []
        
        # 簡易的な矛盾検出
        if primary_domain == 'legal' and 'business' in related_domains:
            contradictions.append({
                'domain1': 'legal',
                'domain2': 'business',
                'issue': 'Different interpretation of contractual obligations',
                'resolution': 'Consider both legal requirements and business practices',
            })
        
        if primary_domain == 'technical' and 'business' in related_domains:
            contradictions.append({
                'domain1': 'technical',
                'domain2': 'business',
                'issue': 'Technical feasibility vs. business timeline',
                'resolution': 'Negotiate trade-offs between quality and schedule',
            })
        
        return contradictions
    
    def _synthesize_knowledge(self, primary_domain: str, 
                             facts: List[Dict],
                             contradictions: List[Dict]) -> str:
        """知識を統合的に説明"""
        synthesis = f"Integrated view on the topic from {primary_domain} perspective:\n\n"
        
        # 主要事実を含める
        primary_facts = [f for f in facts if f['type'] == 'primary']
        if primary_facts:
            synthesis += f"Primary perspective: {primary_facts[0]['fact']}\n\n"
        
        # 支援事実を含める
        supporting_facts = [f for f in facts if f['type'] == 'supporting']
        if supporting_facts:
            synthesis += "Supporting perspectives:\n"
            for fact in supporting_facts:
                synthesis += f"  - {fact['domain']}: {fact['fact']}\n"
        
        # 矛盾がある場合は言及
        if contradictions:
            synthesis += "\nKey considerations and potential contradictions:\n"
            for cont in contradictions:
                synthesis += f"  - {cont['issue']}\n"
                synthesis += f"    Resolution: {cont['resolution']}\n"
        
        return synthesis
    
    def explain_perspective_differences(self, domain1: str, domain2: str, 
                                        topic: str) -> str:
        """ドメイン間の視点の相違を説明"""
        explanation = f"Perspectives on '{topic}':\n\n"
        
        perspective_map = {
            ('medical', 'legal'): {
                'medical': 'Focuses on patient wellness and treatment efficacy',
                'legal': 'Focuses on liability, consent, and regulatory compliance',
            },
            ('technical', 'business'): {
                'technical': 'Focuses on code quality, performance, and scalability',
                'business': 'Focuses on ROI, market time, and customer value',
            },
        }
        
        key = (min(domain1, domain2), max(domain1, domain2))
        if key in perspective_map:
            for domain, perspective in perspective_map[key].items():
                explanation += f"{domain.upper()}: {perspective}\n"
        else:
            explanation += f"{domain1}: Domain-specific perspective\n"
            explanation += f"{domain2}: Domain-specific perspective\n"
        
        return explanation


# ============================================================
# CausalReasoningEngine: 因果推論エンジン
# ============================================================

class CausalReasoningEngine:
    """因果関係・相関関係を分析"""
    
    def __init__(self):
        # ドメイン別の因果知識ベース
        self.causal_knowledge = {
            'medical': [
                ('smoking', 'lung_cancer', 0.9),
                ('high_cholesterol', 'heart_disease', 0.8),
                ('exercise', 'fitness', 0.85),
            ],
            'business': [
                ('market_demand', 'revenue', 0.8),
                ('customer_satisfaction', 'retention', 0.85),
                ('innovation', 'competitive_advantage', 0.7),
            ],
            'technical': [
                ('algorithm_optimization', 'performance_improvement', 0.9),
                ('code_review', 'bug_reduction', 0.7),
            ],
        }
        
        logger.info("CausalReasoningEngine initialized")
    
    def infer_causality(self, fact1: str, fact2: str) -> Optional[CausalRelation]:
        """因果関係を推定"""
        # 簡易的な因果推定
        fact1_lower = fact1.lower()
        fact2_lower = fact2.lower()
        
        # 全ドメインの知識を検索
        for domain, relations in self.causal_knowledge.items():
            for cause, effect, strength in relations:
                if cause in fact1_lower and effect in fact2_lower:
                    return CausalRelation(
                        cause=fact1,
                        effect=fact2,
                        strength=strength,
                        confidence=0.8,
                    )
        
        return None
    
    def trace_causality_chain(self, root_cause: str, max_depth: int = 5) -> List[CausalRelation]:
        """因果チェーンを追跡"""
        chain = []
        current = root_cause
        depth = 0
        
        # 簡易的な因果チェーン構築
        for domain, relations in self.causal_knowledge.items():
            for cause, effect, strength in relations:
                if cause in current.lower():
                    relation = CausalRelation(
                        cause=cause,
                        effect=effect,
                        strength=strength,
                    )
                    chain.append(relation)
                    depth += 1
                    if depth >= max_depth:
                        break
        
        return chain
    
    def identify_confounders(self, effect: str, domain: str) -> List[str]:
        """交絡因子を特定"""
        confounders = []
        
        # ドメイン別の交絡因子知識
        confounder_map = {
            'medical': {
                'health_outcome': ['genetics', 'diet', 'lifestyle', 'environment'],
                'disease': ['age', 'stress', 'immunity', 'socioeconomic_status'],
            },
            'business': {
                'revenue': ['market_condition', 'competition', 'economy', 'seasonality'],
                'growth': ['brand_awareness', 'distribution', 'pricing', 'quality'],
            },
        }
        
        if domain in confounder_map:
            effect_lower = effect.lower()
            for key, factors in confounder_map[domain].items():
                if key in effect_lower:
                    confounders.extend(factors)
        
        return confounders
    
    def counterfactual_analysis(self, scenario: str) -> Dict:
        """反事実分析を実行"""
        analysis = {
            'scenario': scenario,
            'definition': f'If not {scenario}...',
            'likely_outcomes': [],
            'key_differences': [],
        }
        
        # 簡易的な反事実分析
        if 'pandemic' in scenario.lower():
            analysis['likely_outcomes'] = [
                'Uncontrolled disease spread',
                'Healthcare system collapse',
                'Economy continues as normal',
            ]
            analysis['key_differences'] = [
                'Mortality rate would be much higher',
                'No lockdown measures',
                'Different economic impact',
            ]
        
        return analysis


# ============================================================
# UncertaintyManager: 不確実性管理
# ============================================================

class UncertaintyManager:
    """知識の不確実性を管理・表現"""
    
    def __init__(self):
        # 不確実性レベルの基準
        self.uncertainty_thresholds = {
            'certain': (0.0, 0.1),
            'likely': (0.1, 0.3),
            'somewhat_uncertain': (0.3, 0.6),
            'uncertain': (0.6, 0.85),
            'highly_uncertain': (0.85, 1.0),
        }
        
        logger.info("UncertaintyManager initialized")
    
    def assess_uncertainty(self, statement: str, domain: str) -> Uncertainty:
        """ステートメントの不確実性を評価"""
        # 簡易的な不確実性評価
        uncertainty_level = self._calculate_uncertainty_level(statement, domain)
        sources = self._identify_uncertainty_sources(statement, domain)
        alternatives = self._generate_alternatives(statement)
        
        # 信頼区間を計算
        confidence_interval = (
            max(0.0, uncertainty_level - 0.15),
            min(1.0, uncertainty_level + 0.15)
        )
        
        return Uncertainty(
            level=uncertainty_level,
            sources=sources,
            confidence_interval=confidence_interval,
            alternative_interpretations=alternatives,
        )
    
    def _calculate_uncertainty_level(self, statement: str, domain: str) -> float:
        """不確実性レベルを計算"""
        # キーワードベースの簡易的な計算
        uncertainty_indicators = ['maybe', 'possibly', 'probably', 'seems', 'might', 'could']
        certainty_indicators = ['definitely', 'clearly', 'certainly', 'proven', 'established']
        
        statement_lower = statement.lower()
        
        uncertainty_count = sum(1 for ind in uncertainty_indicators 
                              if ind in statement_lower)
        certainty_count = sum(1 for ind in certainty_indicators 
                            if ind in statement_lower)
        
        base_level = 0.5
        adjustment = (uncertainty_count * 0.1) - (certainty_count * 0.1)
        
        return max(0.0, min(1.0, base_level + adjustment))
    
    def _generate_alternatives(self, statement: str) -> List[str]:
        """代替解釈を生成"""
        alternatives = []
        
        # 簡易的な代替解釈生成
        if 'vaccine' in statement.lower():
            alternatives.append('Protection percentage varies by individual factors')
            alternatives.append('Effectiveness may depend on variant strains')
            alternatives.append('Duration of protection may diminish over time')
        
        if 'cause' in statement.lower() or 'caused' in statement.lower():
            alternatives.append('Multiple contributing factors may be involved')
            alternatives.append('The relationship might be correlational, not causal')
            alternatives.append('Temporal sequence may not be as direct as assumed')
        
        if not alternatives:
            alternatives.append('Alternative interpretation 1')
            alternatives.append('Alternative interpretation 2')
        
        return alternatives
    
    def _identify_uncertainty_sources(self, statement: str, domain: str) -> List[str]:
        """不確実性の源を特定"""
        sources = []
        
        statement_lower = statement.lower()
        
        if 'future' in statement_lower or 'predict' in statement_lower:
            sources.append('temporal_distance')
        
        if 'estimate' in statement_lower or 'approximate' in statement_lower:
            sources.append('measurement_limitation')
        
        if 'conflicting' in statement_lower or 'debate' in statement_lower:
            sources.append('conflicting_evidence')
        
        if 'limited' in statement_lower or 'scarce' in statement_lower:
            sources.append('insufficient_data')
        
        if not sources:
            sources.append('general_knowledge_limitation')
        
        return sources
    
    def express_uncertainty(self, uncertainty: Uncertainty) -> str:
        """不確実性を言語化"""
        level = uncertainty.level
        
        if level < 0.15:
            expression = "This is a well-established fact."
        elif level < 0.35:
            expression = "This is likely accurate, with minor uncertainty."
        elif level < 0.60:
            expression = "This is reasonably supported, but has some uncertainties."
        elif level < 0.85:
            expression = "This is somewhat uncertain and subject to debate."
        else:
            expression = "This is highly speculative."
        
        expression += f"\n\nSources of uncertainty: {', '.join(uncertainty.sources)}"
        
        if uncertainty.alternative_interpretations:
            expression += "\n\nAlternative interpretations:"
            for alt in uncertainty.alternative_interpretations:
                expression += f"\n  - {alt}"
        
        return expression
    
    def combine_uncertainties(self, uncertainties: List[Uncertainty]) -> Uncertainty:
        """複数の不確実性を統合"""
        if not uncertainties:
            return Uncertainty(level=0.5)
        
        # 平均不確実性レベルを計算
        avg_level = sum(u.level for u in uncertainties) / len(uncertainties)
        
        # 全ての源を集約
        all_sources = set()
        for u in uncertainties:
            all_sources.update(u.sources)
        
        # 全ての代替解釈を集約
        all_alternatives = []
        for u in uncertainties:
            all_alternatives.extend(u.alternative_interpretations)
        
        return Uncertainty(
            level=avg_level,
            sources=list(all_sources),
            alternative_interpretations=all_alternatives[:5],  # Top 5
        )
    
    def recommend_additional_research(self, uncertainty: Uncertainty) -> List[str]:
        """さらなる研究を推奨"""
        recommendations = []
        
        if 'insufficient_data' in uncertainty.sources:
            recommendations.append('Conduct empirical studies to gather more data')
        
        if 'conflicting_evidence' in uncertainty.sources:
            recommendations.append('Synthesize conflicting findings in a meta-analysis')
        
        if 'temporal_distance' in uncertainty.sources:
            recommendations.append('Develop predictive models with updated assumptions')
        
        if 'measurement_limitation' in uncertainty.sources:
            recommendations.append('Improve measurement methodologies and precision')
        
        if not recommendations:
            recommendations.append('Conduct literature review for deeper understanding')
        
        return recommendations
