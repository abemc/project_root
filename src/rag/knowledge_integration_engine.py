"""
知識統合・推論エンジン
複数ドメインの知識を統合し、因果関係と不確実性を考慮した回答を生成
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from src.self_improvement.reasoning_engine import (
    KnowledgeIntegrator,
    CausalReasoningEngine,
    UncertaintyManager
)
from src.self_improvement.domain_knowledge import DomainKnowledgeManager
from src.rag.query_preprocessor import QueryPreprocessingResult

@dataclass
class IntegratedKnowledgeResult:
    """統合知識の結果"""
    query: str
    primary_domain: str
    related_domains: List[str]
    integrated_knowledge: Dict[str, Any]
    causal_analysis: Dict[str, Any]
    uncertainty_assessment: Dict[str, Any]
    final_answer_template: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'primary_domain': self.primary_domain,
            'related_domains': self.related_domains,
            'integrated_knowledge': self.integrated_knowledge,
            'causal_analysis': self.causal_analysis,
            'uncertainty_assessment': self.uncertainty_assessment,
            'final_answer_template': self.final_answer_template,
            'generated_at': self.generated_at
        }


class Phase7KnowledgeIntegrationEngine:
    """
    Phase 7対応知識統合エンジン
    
    機能:
    - 複数ドメインの知識を統合
    - ドメイン間の矛盾を検出・解決
    - 因果関係を分析
    - 不確実性を定量化
    """
    
    def __init__(self):
        """初期化"""
        self.knowledge_integrator = KnowledgeIntegrator()
        self.causal_engine = CausalReasoningEngine()
        self.uncertainty_manager = UncertaintyManager()
        self.domain_manager = DomainKnowledgeManager()
    
    def integrate_and_reason(
        self,
        preprocessing_result: QueryPreprocessingResult,
        retrieved_documents: Dict[str, List[Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> IntegratedKnowledgeResult:
        """
        マルチドメイン知識を統合し、推論を実行
        
        Args:
            preprocessing_result: クエリ前処理結果
            retrieved_documents: ドメイン別の検索結果 {domain: [documents]}
            user_context: ユーザーコンテキスト（オプション）
        
        Returns:
            統合知識の結果
        """
        
        # 1. ドメイン別知識の抽出
        self._extract_domain_knowledge(retrieved_documents)
        
        # 2. マルチドメイン知識統合
        integrated_result = self.knowledge_integrator.integrate_knowledge(
            primary_domain=preprocessing_result.primary_domain,
            related_domains=preprocessing_result.related_domains,
            query=preprocessing_result.original_query
        )
        
        # 戻り値を辞書に正規化
        if isinstance(integrated_result, dict):
            integrated_knowledge = integrated_result
        else:
            integrated_knowledge = {
                'primary_answer': str(integrated_result) if integrated_result else '',
                'integrated_insights': {},
                'synthesis': getattr(integrated_result, 'synthesis', '')
            }
        
        # 3. ドメイン間矛盾の検出と解決
        contradiction_resolution = self._resolve_domain_contradictions(
            integrated_knowledge,
            preprocessing_result.primary_domain,
            preprocessing_result.related_domains
        )
        
        # 4. 因果関係の分析
        causal_analysis = self._analyze_causality_from_knowledge(
            query=preprocessing_result.original_query,
            knowledge=integrated_knowledge,
            domain=preprocessing_result.primary_domain
        )
        
        # 5. 不確實性の評価
        uncertainty_assessment = self._assess_uncertainty_level(
            statement=integrated_knowledge if isinstance(integrated_knowledge, str) 
                      else "統合された知識",
            domain=preprocessing_result.primary_domain
        )
        
        # 6. 最終回答テンプレートの生成
        final_answer_template = self._generate_answer_template(
            preprocessing_result=preprocessing_result,
            integrated_knowledge=integrated_knowledge,
            causal_analysis=causal_analysis,
            uncertainty_assessment=uncertainty_assessment,
            contradiction_resolution=contradiction_resolution,
            user_context=user_context
        )
        
        return IntegratedKnowledgeResult(
            query=preprocessing_result.original_query,
            primary_domain=preprocessing_result.primary_domain,
            related_domains=preprocessing_result.related_domains,
            integrated_knowledge=integrated_knowledge,
            causal_analysis=causal_analysis,
            uncertainty_assessment=uncertainty_assessment,
            final_answer_template=final_answer_template
        )
    
    def _extract_domain_knowledge(
        self,
        retrieved_documents: Dict[str, List[Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        検索結果からドメイン別知識を抽出
        
        Args:
            retrieved_documents: ドメイン別の検索結果
        
        Returns:
            {domain: {concepts, relationships, facts}}
        """
        domain_knowledge = {}
        
        for domain, documents in retrieved_documents.items():
            concepts = []
            relationships = []
            facts = []
            
            for doc in documents:
                # ドキュメントからテキストを抽出
                text = getattr(doc, 'content', str(doc))
                
                # 簡単な処理（本来はより複雑なNLP処理が必要）
                concepts.extend(self._extract_concepts(text))
                facts.append(text[:100])  # 最初の100文字をファクトとして
            
            domain_knowledge[domain] = {
                'concepts': list(set(concepts)),
                'relationships': relationships,
                'facts': facts,
                'document_count': len(documents)
            }
        
        return domain_knowledge
    
    def _analyze_causality_from_knowledge(
        self,
        query: str,
        knowledge: Dict[str, Any],
        domain: str
    ) -> Dict[str, Any]:
        """
        知識から因果関係を分析
        """
        return {
            'causal_chains': [
                f"{domain}における主要な因果関係を特定"
            ],
            'confidence': 0.6,
            'alternative_causalities': []
        }
    
    def _assess_uncertainty_level(
        self,
        statement: str,
        domain: str
    ) -> Dict[str, Any]:
        """
        不確実性レベルを評価
        """
        return {
            'uncertainty_level': 0.4,  # 0-1の範囲
            'sources': ['一般的な知識限界', 'ドメイン固有の変動性'],
            'alternative_interpretations': [
                f"別の{domain}的解釈も存在します"
            ]
        }
    
    def _extract_concepts(self, text: str, max_concepts: int = 5) -> List[str]:
        """
        テキストから主要概念を抽出
        
        Args:
            text: テキスト
            max_concepts: 最大概念数
        
        Returns:
            概念リスト
        """
        # 簡易的な概念抽出（本来はより高度な処理）
        words = text.split()
        # 名詞っぽい単語（大文字で始まる、3文字以上）をフィルタ
        concepts = [w for w in words if len(w) >= 3 and w[0].isupper()]
        return concepts[:max_concepts]
    
    def _resolve_domain_contradictions(
        self,
        integrated_knowledge: Dict[str, Any],
        primary_domain: str,
        related_domains: List[str]
    ) -> Dict[str, Any]:
        """
        ドメイン間の矛盾を検出・解決
        
        Args:
            integrated_knowledge: 統合知識
            primary_domain: 主要ドメイン
            related_domains: 関連ドメイン
        
        Returns:
            矛盾解決の結果
        """
        contradictions = []
        resolutions = []
        
        # 簡易的な矛盾検出（本来はより複雑）
        insights = integrated_knowledge.get('integrated_insights', {})
        
        # 異なるドメイン間での見方の違いを記録
        for domain in [primary_domain] + related_domains:
            domain_specific = insights.get(f'{domain}_perspective', '')
            if domain_specific:
                contradictions.append({
                    'domain': domain,
                    'perspective': domain_specific
                })
        
        # 矛盾の解決方針を生成
        if contradictions:
            resolutions.append(
                f"{len(contradictions)}個のドメインから統合的に検討することで、"
                "より完全な理解が可能になります"
            )
        
        return {
            'detected_contradictions': contradictions,
            'resolutions': resolutions,
            'resolution_count': len(resolutions)
        }
    
    def _generate_answer_template(
        self,
        preprocessing_result: QueryPreprocessingResult,
        integrated_knowledge: Dict[str, Any],
        causal_analysis: Dict[str, Any],
        uncertainty_assessment: Dict[str, Any],
        contradiction_resolution: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        最終回答テンプレートを生成
        
        Args:
            preprocessing_result: クエリ前処理結果
            integrated_knowledge: 統合知識
            causal_analysis: 因果分析
            uncertainty_assessment: 不確実性評価
            contradiction_resolution: 矛盾解決
            user_context: ユーザーコンテキスト
        
        Returns:
            回答テンプレート
        """
        template = []
        
        # 1. 主要な回答
        primary_answer = integrated_knowledge.get('primary_answer', '')
        if primary_answer:
            template.append(f"【主要な回答】\n{primary_answer}")
        
        # 2. 複数ドメイン視点（必要な場合）
        if len(preprocessing_result.related_domains) > 0:
            template.append("\n【マルチドメイン視点】")
            for domain in [preprocessing_result.primary_domain] + preprocessing_result.related_domains:
                perspective = integrated_knowledge.get(
                    'integrated_insights', {}
                ).get(f'{domain}_perspective', '')
                if perspective:
                    template.append(f"- {domain}の観点: {perspective}")
        
        # 3. 因果関係（必要な場合）
        if preprocessing_result.complexity_level in ['MODERATE', 'COMPLEX']:
            causal_chains = causal_analysis.get('causal_chains', [])
            if causal_chains:
                template.append("\n【因果関係】")
                for chain in causal_chains[:3]:  # 最初の3つまで
                    template.append(f"- {chain}")
        
        # 4. 不確実性の明示（隠れた意図に応じて）
        if 'learn_methodology' in preprocessing_result.implicit_intents:
            uncertainty_level = uncertainty_assessment.get('uncertainty_level', 0.5)
            if uncertainty_level > 0.3:
                template.append("\n【不確実性について】")
                alternative_interpretations = uncertainty_assessment.get(
                    'alternative_interpretations', []
                )
                for interpretation in alternative_interpretations[:2]:
                    template.append(f"- {interpretation}")
        
        # 5. 矛盾の説明（関連ドメインが複数の場合）
        if contradiction_resolution.get('resolution_count', 0) > 0:
            template.append("\n【ドメイン間の相違について】")
            for resolution in contradiction_resolution.get('resolutions', []):
                template.append(f"- {resolution}")
        
        # 6. ユーザー知識レベルに応じた追加説明
        if user_context and user_context.get('knowledge_level') == 'beginner':
            template.append("\n【基本的な背景】")
            template.append("- より詳しく知りたい場合はお知らせください")
        
        return "\n".join(template)


class ResponseGenerationEngine:
    """
    最終応答生成エンジン
    統合知識から自然な応答文を生成
    """
    
    def __init__(self):
        """初期化"""
        self.knowledge_engine = Phase7KnowledgeIntegrationEngine()
    
    def generate_response(
        self,
        integrated_result: IntegratedKnowledgeResult,
        base_llm_response: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        最終応答を生成
        
        Args:
            integrated_result: 統合知識の結果
            base_llm_response: LLMの基本応答
            user_context: ユーザーコンテキスト
        
        Returns:
            最終応答テキスト
        """
        
        # 1. テンプレートに基づいて構造化された応答を生成
        answer_template = integrated_result.final_answer_template
        
        # 2. LLMの応答と統合
        structured_response = self._enhance_with_template(
            base_response=base_llm_response,
            template=answer_template
        )
        
        # 3. ユーザー知識レベルに応じた調整
        if user_context:
            knowledge_level = user_context.get('knowledge_level', 'intermediate')
            structured_response = self._adjust_for_knowledge_level(
                response=structured_response,
                knowledge_level=knowledge_level
            )
        
        # 4. 不確実性を適切に表現
        structured_response = self._express_uncertainty(
            response=structured_response,
            uncertainty_assessment=integrated_result.uncertainty_assessment
        )
        
        return structured_response
    
    def _enhance_with_template(
        self,
        base_response: str,
        template: str
    ) -> str:
        """
        テンプレートで基本応答を強化
        """
        if not template:
            return base_response
        
        # テンプレートとLLMの応答を組み合わせ
        enhanced = f"{base_response}\n\n【詳細な分析】\n{template}"
        return enhanced
    
    def _adjust_for_knowledge_level(
        self,
        response: str,
        knowledge_level: str
    ) -> str:
        """
        知識レベルに応じた調整
        """
        if knowledge_level == 'beginner':
            # 専門用語を簡略化（実装は簡易版）
            response = response.replace('統計的', '数値的：')
            response = response.replace('メカニズム', 'しくみ')
        
        return response
    
    def _express_uncertainty(
        self,
        response: str,
        uncertainty_assessment: Dict[str, Any]
    ) -> str:
        """
        不確実性を適切に表現
        """
        uncertainty_level = uncertainty_assessment.get('uncertainty_level', 0.0)
        
        if uncertainty_level > 0.7:
            prefix = "【注意】以下の情報には高い不確実性があります：\n"
            response = prefix + response
        elif uncertainty_level > 0.4:
            prefix = "【参考】以下は一般的な理解に基づいています：\n"
            response = prefix + response
        
        return response


class KnowledgeEnrichmentManager:
    """
    知識の充実化管理
    検索結果から得られた知識を拡張・補強
    """
    
    def __init__(self):
        """初期化"""
        self.domain_manager = DomainKnowledgeManager()
    
    def enrich_knowledge(
        self,
        base_knowledge: Dict[str, Any],
        implicit_intents: Dict[str, Any],
        required_domains: List[str]
    ) -> Dict[str, Any]:
        """
        知識を充実化
        
        Args:
            base_knowledge: 基本知識
            implicit_intents: 隠れた意図
            required_domains: 必要なドメイン
        
        Returns:
            充実化された知識
        """
        enriched = base_knowledge.copy()
        
        # 1. 隠れた意図に基づいて追加情報を要求
        if 'learn_methodology' in implicit_intents:
            enriched['methodology'] = self._add_methodology_info(
                base_knowledge,
                required_domains
            )
        
        if 'explore_implications' in implicit_intents:
            enriched['implications'] = self._add_implications(
                base_knowledge,
                required_domains
            )
        
        # 2. ドメイン間の架け橋概念を追加
        enriched['bridge_concepts'] = self._find_bridge_concepts(
            required_domains
        )
        
        return enriched
    
    def _add_methodology_info(
        self,
        knowledge: Dict[str, Any],
        domains: List[str]
    ) -> Dict[str, Any]:
        """
        方法論情報を追加
        """
        return {
            'methodology': f"{len(domains)}個のドメインから統合的に検討",
            'steps': ['背景理解', 'ドメイン別分析', '統合的解釈']
        }
    
    def _add_implications(
        self,
        knowledge: Dict[str, Any],
        domains: List[str]
    ) -> Dict[str, Any]:
        """
        含意を追加
        """
        return {
            'short_term': '当面の影響は限定的',
            'long_term': '長期的には複雑な相互作用が考えられます',
            'domain_specific': {domain: f"{domain}への影響" for domain in domains}
        }
    
    def _find_bridge_concepts(
        self,
        domains: List[str]
    ) -> Dict[str, Any]:
        """
        ドメイン間の架け橋概念を発見
        """
        bridge_concepts = {}
        
        # 簡易的な架け橋概念マッピング
        bridge_map = {
            ('medical', 'legal'): ['medical_evidence', 'liability', 'standard_of_care'],
            ('technical', 'business'): ['cost_benefit', 'implementation', 'ROI'],
            ('business', 'legal'): ['compliance', 'regulations', 'contracts'],
        }
        
        for (d1, d2) in bridge_map:
            if d1 in domains and d2 in domains:
                bridge_concepts[f'{d1}-{d2}'] = bridge_map[(d1, d2)]
        
        return bridge_concepts
