"""
ドメイン特化モデル開発

複数ドメイン対応、ドメイン検出、特化アダプター実装
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


class DomainType(Enum):
    """ドメインタイプ"""
    LEGAL = "legal"  # 法務
    MEDICAL = "medical"  # 医療
    TECHNICAL = "technical"  # 技術
    FINANCIAL = "financial"  # 金融
    GENERAL = "general"  # 一般


class SpecializationLevel(Enum):
    """特化レベル"""
    BASE = "base"  # 基本
    INTERMEDIATE = "intermediate"  # 中級
    EXPERT = "expert"  # 専門家レベル


@dataclass
class DomainVocabulary:
    """ドメイン用語集"""
    domain: DomainType
    terms: Dict[str, str] = field(default_factory=dict)  # term -> definition
    synonyms: Dict[str, List[str]] = field(default_factory=dict)  # term -> synonyms
    abbreviations: Dict[str, str] = field(default_factory=dict)  # abbr -> full form
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_term(self, term: str, definition: str, synonyms: Optional[List[str]] = None) -> None:
        """用語を追加"""
        self.terms[term] = definition
        if synonyms:
            self.synonyms[term] = synonyms
    
    def get_term_definition(self, term: str) -> Optional[str]:
        """用語定義を取得"""
        return self.terms.get(term)


@dataclass
class DomainAdapter:
    """ドメインアダプター設定"""
    domain: DomainType
    adapter_name: str
    lora_rank: int = 16
    lora_alpha: int = 32
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "v_proj"]
    )
    parameters_count: int = 0
    specialization_level: SpecializationLevel = SpecializationLevel.INTERMEDIATE


@dataclass
class DomainBenchmark:
    """ドメイン別ベンチマーク"""
    domain: DomainType
    task_name: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    inference_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class DomainDetector:
    """ドメイン検出エンジン"""
    
    def __init__(self):
        """初期化"""
        self.domain_keywords: Dict[DomainType, List[str]] = {
            DomainType.LEGAL: [
                "contract", "lawsuit", "defendant", "plaintiff", "verdict",
                "attorney", "legal", "law", "clause", "agreement"
            ],
            DomainType.MEDICAL: [
                "patient", "diagnosis", "treatment", "disease", "symptom",
                "doctor", "clinical", "medical", "hospital", "medication"
            ],
            DomainType.TECHNICAL: [
                "algorithm", "code", "api", "database", "server",
                "deployment", "debug", "function", "module", "architecture"
            ],
            DomainType.FINANCIAL: [
                "investment", "portfolio", "stock", "dividend", "market",
                "financial", "revenue", "profit", "balance sheet", "forecast"
            ]
        }
        self.detection_scores: Dict[str, float] = {}
    
    def detect_domain(self, text: str) -> DomainType:
        """テキストからドメインを検出"""
        
        text_lower = text.lower()
        domain_scores = {}
        
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            domain_scores[domain] = score
        
        # スコアが最も高いドメインを選択
        if max(domain_scores.values()) > 0:
            detected_domain = max(domain_scores, key=domain_scores.get)
            logger.info(f"Domain detected: {detected_domain.value} (score: {domain_scores[detected_domain]})")
            return detected_domain
        
        logger.info("No specific domain detected, using GENERAL")
        return DomainType.GENERAL
    
    def get_domain_confidence(self, text: str, domain: DomainType) -> float:
        """ドメイン検出の信頼度を取得（0-1）"""
        
        text_lower = text.lower()
        keywords = self.domain_keywords.get(domain, [])
        
        if not keywords:
            return 0.0
        
        matched = sum(1 for keyword in keywords if keyword in text_lower)
        confidence = min(matched / len(keywords), 1.0)
        
        return confidence


class DomainAdapter:
    """ドメイン特化アダプター"""
    
    def __init__(
        self,
        domain: DomainType,
        adapter_config: DomainAdapter
    ):
        """初期化"""
        self.domain = domain
        self.config = adapter_config
        self.weights: Dict[str, Any] = {}
        self.metrics: List[DomainBenchmark] = []
        self.active = False
    
    async def load_weights(self, weights_path: str) -> bool:
        """アダプター重みを読み込み"""
        
        try:
            # ウェイトファイルを読み込む（シミュレーション）
            self.weights = {
                f"adapter_{i}": {"weight": i * 0.1}
                for i in range(5)
            }
            logger.info(f"Loaded weights for {self.domain.value} adapter")
            return True
        except Exception as e:
            logger.error(f"Failed to load weights: {e}")
            return False
    
    async def enable(self) -> None:
        """アダプターを有効化"""
        self.active = True
        logger.info(f"Enabled {self.domain.value} adapter")
    
    async def disable(self) -> None:
        """アダプターを無効化"""
        self.active = False
        logger.info(f"Disabled {self.domain.value} adapter")
    
    async def add_benchmark(self, benchmark: DomainBenchmark) -> None:
        """ベンチマーク結果を追加"""
        self.metrics.append(benchmark)
        logger.info(
            f"Benchmark added for {benchmark.task_name}: "
            f"Accuracy={benchmark.accuracy:.2%}, F1={benchmark.f1_score:.2%}"
        )


class DomainSpecificPrompter:
    """ドメイン特化プロンプティングシステム"""
    
    def __init__(self):
        """初期化"""
        self.domain_prompts: Dict[DomainType, Dict[str, str]] = {
            DomainType.LEGAL: {
                "analyze_contract": """Analyze this legal contract focusing on:
1. Key obligations and rights
2. Liability limitations
3. Termination clauses
4. Dispute resolution mechanisms
Provide a structured analysis suitable for legal review.""",
                "question_answering": """Answer this legal question with precision:
- Cite relevant statutes or precedents if applicable
- Distinguish between general principles and specific exceptions
- Clearly state assumptions made in your answer"""
            },
            DomainType.MEDICAL: {
                "diagnosis_assistance": """Based on the symptoms described:
1. List differential diagnoses in order of likelihood
2. Suggest diagnostic tests needed
3. Note any red flags requiring immediate attention
4. Recommend specialist referral if appropriate""",
                "question_answering": """Answer this medical question with accuracy:
- Reference clinical guidelines or evidence-based practices
- Distinguish between general information and case-specific advice
- Note contraindications or special considerations"""
            },
            DomainType.TECHNICAL: {
                "code_review": """Review this code for:
1. Correctness and potential bugs
2. Performance optimization opportunities
3. Code quality and readability
4. Security vulnerabilities
Provide specific, actionable recommendations.""",
                "architecture_design": """Design a technical architecture that:
1. Meets stated requirements
2. Follows best practices for scalability
3. Includes proper error handling
4. Considers monitoring and debugging needs"""
            },
            DomainType.FINANCIAL: {
                "investment_analysis": """Analyze this investment opportunity:
1. Risk assessment (market, credit, liquidity)
2. Return potential and expected value
3. Portfolio fit and diversification benefits
4. Comparison with alternatives""",
                "question_answering": """Answer this financial question:
- Use current market data or standard assumptions if needed
- Distinguish between general principles and specific circumstances
- Consider tax and regulatory implications"""
            }
        }
    
    def get_domain_prompt(
        self,
        domain: DomainType,
        task_type: str
    ) -> Optional[str]:
        """ドメイン特化プロンプトを取得"""
        
        domain_tasks = self.domain_prompts.get(domain, {})
        return domain_tasks.get(task_type)
    
    def augment_query(
        self,
        query: str,
        domain: DomainType,
        task_type: str
    ) -> str:
        """クエリをドメイン特化で拡張"""
        
        domain_prompt = self.get_domain_prompt(domain, task_type)
        
        if domain_prompt:
            augmented = f"{domain_prompt}\n\nUser Query: {query}"
        else:
            augmented = query
        
        return augmented


class DomainKnowledgeRetriever:
    """ドメイン知識検索エンジン"""
    
    def __init__(self):
        """初期化"""
        self.domain_knowledge: Dict[DomainType, List[Dict[str, Any]]] = {
            DomainType.LEGAL: [
                {"title": "Contract Law Basics", "content": "..."},
                {"title": "Liability Limitations", "content": "..."}
            ],
            DomainType.MEDICAL: [
                {"title": "Diagnosis Guidelines", "content": "..."},
                {"title": "Treatment Protocols", "content": "..."}
            ],
            DomainType.TECHNICAL: [
                {"title": "System Design Patterns", "content": "..."},
                {"title": "Performance Optimization", "content": "..."}
            ],
            DomainType.FINANCIAL: [
                {"title": "Investment Strategies", "content": "..."},
                {"title": "Risk Management", "content": "..."}
            ]
        }
    
    async def retrieve_context(
        self,
        query: str,
        domain: DomainType,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """ドメイン知識を検索"""
        
        knowledge_base = self.domain_knowledge.get(domain, [])
        
        # シンプルなキーワード検索（実装では ベクトル検索）
        results = []
        query_lower = query.lower()
        
        for doc in knowledge_base:
            if any(keyword in doc["title"].lower() or keyword in doc["content"].lower()
                   for keyword in query_lower.split()):
                results.append(doc)
        
        # top_k個を返す
        return results[:top_k]


class DomainQualityAssurance:
    """ドメイン別品質保証"""
    
    def __init__(self):
        """初期化"""
        self.qa_rules: Dict[DomainType, List[Callable]] = {}
        self.quality_scores: Dict[str, float] = {}
    
    async def validate_output(
        self,
        output: str,
        domain: DomainType
    ) -> Dict[str, Any]:
        """出力を検証"""
        
        validation_result = {
            "valid": True,
            "domain": domain.value,
            "checks_passed": 0,
            "checks_total": 0,
            "issues": []
        }
        
        # ドメイン別の検証ルール
        if domain == DomainType.LEGAL:
            validation_result["checks_total"] = 3
            
            # チェック1: 法的用語の正確性
            if self._check_legal_terminology(output):
                validation_result["checks_passed"] += 1
            else:
                validation_result["issues"].append("Inaccurate legal terminology")
            
            # チェック2: 矛盾の検出
            if not self._has_contradictions(output):
                validation_result["checks_passed"] += 1
            else:
                validation_result["issues"].append("Logical contradictions found")
            
            # チェック3: 参照の完全性
            if self._has_proper_references(output):
                validation_result["checks_passed"] += 1
            else:
                validation_result["issues"].append("Missing proper legal references")
        
        elif domain == DomainType.MEDICAL:
            validation_result["checks_total"] = 3
            
            # チェック1: 医学用語の正確性
            if self._check_medical_terminology(output):
                validation_result["checks_passed"] += 1
            
            # チェック2: 安全性警告
            if self._has_safety_warnings(output):
                validation_result["checks_passed"] += 1
            
            # チェック3: 免責事項
            if self._has_disclaimers(output):
                validation_result["checks_passed"] += 1
        
        validation_result["valid"] = validation_result["checks_passed"] >= validation_result["checks_total"] * 0.7
        
        return validation_result
    
    def _check_legal_terminology(self, text: str) -> bool:
        """法的用語をチェック"""
        legal_terms = ["party", "agreement", "consideration", "breach", "liability"]
        return any(term in text.lower() for term in legal_terms)
    
    def _check_medical_terminology(self, text: str) -> bool:
        """医学用語をチェック"""
        medical_terms = ["symptom", "diagnosis", "treatment", "clinical", "patient"]
        return any(term in text.lower() for term in medical_terms)
    
    def _has_contradictions(self, text: str) -> bool:
        """矛盾を検出"""
        # シンプルな実装
        return "however" not in text.lower() or "but" not in text.lower()
    
    def _has_proper_references(self, text: str) -> bool:
        """適切な参照があるか"""
        return any(indicator in text for indicator in ["cited", "reference", "statute", "precedent"])
    
    def _has_safety_warnings(self, text: str) -> bool:
        """安全警告があるか"""
        return any(warning in text.lower() for warning in ["consult", "professional", "warning", "caution"])
    
    def _has_disclaimers(self, text: str) -> bool:
        """免責事項があるか"""
        return any(disclaimer in text.lower() for disclaimer in ["not a", "disclaimer", "not intended", "not medical advice"])


class DomainModelManager:
    """ドメインモデル統合管理"""
    
    def __init__(self):
        """初期化"""
        self.detector = DomainDetector()
        self.adapters: Dict[DomainType, DomainAdapter] = {}
        self.prompter = DomainSpecificPrompter()
        self.knowledge_retriever = DomainKnowledgeRetriever()
        self.qa = DomainQualityAssurance()
    
    async def register_domain_adapter(
        self,
        adapter: DomainAdapter
    ) -> bool:
        """ドメインアダプターを登録"""
        
        try:
            self.adapters[adapter.config.domain] = adapter
            logger.info(f"Registered adapter for {adapter.config.domain.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to register adapter: {e}")
            return False
    
    async def process_query(
        self,
        query: str,
        task_type: str = "general"
    ) -> Dict[str, Any]:
        """ドメイン対応クエリ処理"""
        
        # ドメイン検出
        detected_domain = self.detector.detect_domain(query)
        confidence = self.detector.get_domain_confidence(query, detected_domain)
        
        # プロンプト拡張
        augmented_query = self.prompter.augment_query(query, detected_domain, task_type)
        
        # ドメイン知識検索
        context = await self.knowledge_retriever.retrieve_context(
            query,
            detected_domain,
            top_k=3
        )
        
        return {
            "detected_domain": detected_domain.value,
            "confidence": confidence,
            "augmented_query": augmented_query,
            "domain_context": context,
            "adapter_active": detected_domain in self.adapters and self.adapters[detected_domain].active
        }
    
    async def get_domain_report(self) -> Dict[str, Any]:
        """ドメイン別レポートを取得"""
        
        report = {
            "registered_domains": len(self.adapters),
            "adapters": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for domain, adapter in self.adapters.items():
            report["adapters"][domain.value] = {
                "active": adapter.active,
                "specialization_level": adapter.config.specialization_level.value,
                "benchmarks_count": len(adapter.metrics),
                "average_accuracy": (
                    sum(b.accuracy for b in adapter.metrics) / len(adapter.metrics)
                    if adapter.metrics else 0.0
                )
            }
        
        return report
