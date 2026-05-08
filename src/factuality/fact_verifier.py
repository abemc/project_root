"""
ファクトチェッカー実装
主要機能:
- ファクトクレイム抽出 (NER + 依存関係分析)
- エビデンスベース検索 (複数ソース対応)
- ファクトチェック実行 (複合スコアリング)
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class FactCheckStatus(Enum):
    """ファクトチェック結果ステータス"""
    VERIFIED = "verified"           # 検証済み（真）
    PARTIALLY_VERIFIED = "partially_verified"  # 部分的に検証済み
    CONTRADICTED = "contradicted"   # 矛盾
    NOT_ENOUGH_INFO = "not_enough_info"  # 情報不足
    UNVERIFIABLE = "unverifiable"   # 検証不可能
    CONFLICTING = "conflicting"     # 複数の矛盾する情報


class EntityType(Enum):
    """エンティティタイプ"""
    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    DATE = "date"
    NUMBER = "number"
    FACT = "fact"
    EVENT = "event"
    PRODUCT = "product"
    OTHER = "other"


@dataclass
class FactClaim:
    """ファクトクレイム（主張）"""
    text: str
    subject: str  # クレイムの対象
    predicate: str  # 述部
    object: str  # オブジェクト
    confidence: float  # 抽出信頼度 (0-1)
    entities: List[Tuple[str, EntityType]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    temporal_info: Optional[str] = None
    source_doc: Optional[str] = None
    
    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


@dataclass
class Evidence:
    """エビデンス（証拠）"""
    text: str
    source: str  # Wikipedia, 公式サイト等
    reliability_score: float  # ソース信頼度 (0-1)
    date_published: Optional[str] = None
    url: Optional[str] = None
    match_score: float = 0.0  # クレイムとの一致度
    contradiction_level: float = 0.0  # 矛盾度 (0=一致, 1=完全矛盾)
    
    def __repr__(self):
        return f"Evidence(source={self.source}, score={self.reliability_score:.2f})"


@dataclass
class FactCheckResult:
    """ファクトチェック結果"""
    claim_text: str
    status: FactCheckStatus
    confidence: float  # 最終信頼度スコア (0-1)
    evidence_for: List[Evidence] = field(default_factory=list)
    evidence_against: List[Evidence] = field(default_factory=list)
    conflicting_evidence: List[Evidence] = field(default_factory=list)
    explanation: str = ""
    reasoning_chain: List[str] = field(default_factory=list)
    primary_source: Optional[str] = None
    alternative_facts: List[str] = field(default_factory=list)
    check_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def total_evidence_count(self) -> int:
        """総エビデンス数"""
        return len(self.evidence_for) + len(self.evidence_against) + len(self.conflicting_evidence)
    
    @property
    def verification_ratio(self) -> float:
        """検証率（検証済みエビデンス数 / 総エビデンス数）"""
        if self.total_evidence_count == 0:
            return 0.0
        verified = len(self.evidence_for)
        return verified / self.total_evidence_count
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "claim": self.claim_text,
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence_for_count": len(self.evidence_for),
            "evidence_against_count": len(self.evidence_against),
            "conflicting_count": len(self.conflicting_evidence),
            "verification_ratio": self.verification_ratio,
            "explanation": self.explanation,
            "primary_source": self.primary_source,
            "alternative_facts": self.alternative_facts,
            "timestamp": self.check_timestamp,
        }


class ClaimExtractor(ABC):
    """クレイム抽出の抽象基底クラス"""
    
    @abstractmethod
    def extract_claims(self, text: str) -> List[FactClaim]:
        """テキストからクレイムを抽出"""
        pass


class SimpleClaimExtractor(ClaimExtractor):
    """シンプルなクレイム抽出器"""
    
    def __init__(self):
        # 一般的なクレイムパターン
        self.claim_patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|was|are|were)\s+([^.!?]+)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:has|have|had)\s+([^.!?]+)",
            r"(?:The|A)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([^.!?]+)",
        ]
        
        # 述語パターン
        self.predicate_keywords = {
            "是": ["is", "was", "are", "were"],
            "所有": ["has", "have", "had", "owns", "owns"],
            "実行": ["did", "do", "does", "made", "make"],
            "時間": ["happened", "occurred", "took place", "was born"],
            "場所": ["located", "situated", "found", "live", "lives"],
        }
    
    def extract_claims(self, text: str) -> List[FactClaim]:
        """シンプルな抽出: 文を分割してクレイムとして認識"""
        claims = []
        sentences = re.split(r'[.!?]\s+', text)
        
        for sent_idx, sentence in enumerate(sentences):
            if len(sentence.strip()) < 10:
                continue
            
            # 簡易的なエンティティ抽出
            entities = self._extract_entities(sentence)
            keywords = self._extract_keywords(sentence)
            
            # クレイムを作成
            claim = FactClaim(
                text=sentence.strip(),
                subject=entities[0][0] if entities else "Unknown",
                predicate="states",
                object=sentence.strip(),
                confidence=0.7 + 0.1 * (len(entities) / max(1, len(entities))),
                entities=entities,
                keywords=keywords,
                source_doc=f"sentence_{sent_idx}",
            )
            claims.append(claim)
        
        return claims
    
    def _extract_entities(self, text: str) -> List[Tuple[str, EntityType]]:
        """簡易的なエンティティ抽出"""
        entities = []
        
        # 数字検出
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        for num in numbers:
            entities.append((num, EntityType.NUMBER))
        
        # 固有名詞（大文字から始まる単語）
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for noun in proper_nouns[:3]:  # 最初の3つのみ
            entities.append((noun, EntityType.PERSON))  # 簡略化
        
        return entities
    
    def _extract_keywords(self, text: str) -> List[str]:
        """キーワード抽出"""
        # ストップワード
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'is', 'are', 'was', 'were'}
        
        words = text.lower().split()
        keywords = [w.strip('.,!?;:') for w in words if w.lower() not in stopwords and len(w) > 3]
        
        return list(set(keywords))[:5]


class EvidenceSearcher(ABC):
    """エビデンス検索の抽象基底クラス"""
    
    @abstractmethod
    async def search(self, claim: FactClaim, limit: int = 5) -> List[Evidence]:
        """クレイムに対するエビデンスを検索"""
        pass


class MockEvidenceSearcher(EvidenceSearcher):
    """モック用エビデンス検索器（テスト用）"""
    
    def __init__(self):
        # テスト用のモックデータベース
        self.knowledge_base = {
            "Paris": [
                Evidence(
                    text="Paris is the capital of France",
                    source="Wikipedia",
                    reliability_score=0.95,
                    date_published="2024-01-01",
                    url="https://en.wikipedia.org/wiki/Paris",
                    match_score=0.95,
                ),
                Evidence(
                    text="Paris is located in northern France",
                    source="Official France Guide",
                    reliability_score=0.9,
                    date_published="2024-02-15",
                    match_score=0.88,
                ),
            ],
            "Tokyo": [
                Evidence(
                    text="Tokyo is the capital and largest city of Japan",
                    source="Wikipedia",
                    reliability_score=0.95,
                    date_published="2024-01-10",
                    match_score=0.92,
                ),
            ],
            "Einstein": [
                Evidence(
                    text="Albert Einstein developed the theory of relativity",
                    source="Physics Encyclopedia",
                    reliability_score=0.98,
                    date_published="2023-06-01",
                    match_score=0.85,
                ),
            ],
        }
    
    async def search(self, claim: FactClaim, limit: int = 5) -> List[Evidence]:
        """モックデータから検索"""
        results = []
        
        # クレイムのサブジェクトで検索
        if claim.subject in self.knowledge_base:
            results = self.knowledge_base[claim.subject][:limit]
        
        # キーワード検索
        for keyword in claim.keywords[:3]:
            if keyword.capitalize() in self.knowledge_base:
                for evidence in self.knowledge_base[keyword.capitalize()][:2]:
                    if evidence not in results and len(results) < limit:
                        results.append(evidence)
        
        return results


class ConfidenceAggregator:
    """複数のエビデンスから最終信頼度を計算"""
    
    @staticmethod
    def compute_confidence(
        evidence_for: List[Evidence],
        evidence_against: List[Evidence],
        conflicting_evidence: List[Evidence],
    ) -> float:
        """
        複合スコアリングで最終信頼度を計算
        
        スコア計算:
        - for: +証拠の信頼度合計
        - against: -証拠の信頼度合計
        - conflicting: 矛盾度に基づくペナルティ
        """
        if not (evidence_for or evidence_against or conflicting_evidence):
            return 0.5  # 不確定
        
        # 各カテゴリのスコア計算
        for_score = sum(e.reliability_score * e.match_score for e in evidence_for) / max(1, len(evidence_for))
        against_score = sum(e.reliability_score for e in evidence_against) / max(1, len(evidence_against))
        
        # 矛盾ペナルティ
        conflict_penalty = 0.0
        if conflicting_evidence:
            conflict_penalty = sum(e.contradiction_level for e in conflicting_evidence) / len(conflicting_evidence)
        
        # 最終スコア計算
        # for_scoreが高く、against_scoreが低く、矛盾が少ないほど高スコア
        confidence = (for_score - against_score * 0.5 - conflict_penalty * 0.3) / 1.8
        
        return max(0.0, min(1.0, confidence))
    
    @staticmethod
    def determine_status(
        for_count: int,
        against_count: int,
        conflicting_count: int,
        confidence: float,
    ) -> FactCheckStatus:
        """エビデンスから最終ステータスを判定"""
        
        # 矛盾がある場合
        if conflicting_count > 0 and against_count > for_count:
            return FactCheckStatus.CONFLICTING
        
        # エビデンスがない場合
        if for_count + against_count + conflicting_count == 0:
            return FactCheckStatus.UNVERIFIABLE
        
        # 肯定エビデンス > 否定エビデンス
        if for_count > against_count * 2:
            if confidence > 0.8:
                return FactCheckStatus.VERIFIED
            elif confidence > 0.6:
                return FactCheckStatus.PARTIALLY_VERIFIED
            else:
                return FactCheckStatus.NOT_ENOUGH_INFO
        
        # 否定エビデンス > 肯定エビデンス
        elif against_count > for_count * 2:
            return FactCheckStatus.CONTRADICTED
        
        # ほぼ同等
        else:
            if confidence > 0.7:
                return FactCheckStatus.PARTIALLY_VERIFIED
            else:
                return FactCheckStatus.NOT_ENOUGH_INFO


class FactVerifier:
    """メインファクトチェッカー"""
    
    def __init__(
        self,
        claim_extractor: Optional[ClaimExtractor] = None,
        evidence_searcher: Optional[EvidenceSearcher] = None,
    ):
        self.claim_extractor = claim_extractor or SimpleClaimExtractor()
        self.evidence_searcher = evidence_searcher or MockEvidenceSearcher()
        self.confidence_aggregator = ConfidenceAggregator()
        self.check_cache: Dict[str, FactCheckResult] = {}
    
    async def verify_text(self, text: str, use_cache: bool = True) -> List[FactCheckResult]:
        """テキスト内のすべてのファクトをチェック"""
        results = []
        
        # クレイム抽出
        claims = self.claim_extractor.extract_claims(text)
        
        # 各クレイムをチェック
        for claim in claims:
            result = await self.check_claim(claim, use_cache=use_cache)
            results.append(result)
        
        return results
    
    async def check_claim(self, claim: FactClaim, use_cache: bool = True) -> FactCheckResult:
        """単一のクレイムをチェック"""
        
        # キャッシュ確認
        cache_key = f"{claim.subject}:{claim.predicate}:{claim.object}"
        if use_cache and cache_key in self.check_cache:
            return self.check_cache[cache_key]
        
        # エビデンス検索
        evidence_results = await self.evidence_searcher.search(claim)
        
        # エビデンスを分類
        evidence_for = []
        evidence_against = []
        conflicting_evidence = []
        
        for evidence in evidence_results:
            if evidence.contradiction_level > 0.7:
                evidence_against.append(evidence)
            elif evidence.contradiction_level > 0.3:
                conflicting_evidence.append(evidence)
            else:
                evidence_for.append(evidence)
        
        # スコア計算
        confidence = self.confidence_aggregator.compute_confidence(
            evidence_for, evidence_against, conflicting_evidence
        )
        
        # ステータス判定
        status = self.confidence_aggregator.determine_status(
            len(evidence_for),
            len(evidence_against),
            len(conflicting_evidence),
            confidence,
        )
        
        # 説明を生成
        explanation = self._generate_explanation(
            claim, evidence_for, evidence_against, conflicting_evidence, confidence
        )
        
        # 結果を作成
        result = FactCheckResult(
            claim_text=claim.text,
            status=status,
            confidence=confidence,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            conflicting_evidence=conflicting_evidence,
            explanation=explanation,
            primary_source=evidence_for[0].source if evidence_for else None,
        )
        
        # キャッシュに保存
        self.check_cache[cache_key] = result
        
        return result
    
    def _generate_explanation(
        self,
        claim: FactClaim,
        evidence_for: List[Evidence],
        evidence_against: List[Evidence],
        conflicting_evidence: List[Evidence],
        confidence: float,
    ) -> str:
        """ファクトチェック結果の説明を生成"""
        parts = [f"ファクト: {claim.text}"]
        parts.append(f"信頼度: {confidence:.1%}")
        
        if evidence_for:
            parts.append(f"サポーティング証拠: {len(evidence_for)}件")
            for e in evidence_for[:2]:
                parts.append(f"  - {e.source}: {e.text[:80]}...")
        
        if evidence_against:
            parts.append(f"矛盾する証拠: {len(evidence_against)}件")
            for e in evidence_against[:2]:
                parts.append(f"  - {e.source}: {e.text[:80]}...")
        
        if conflicting_evidence:
            parts.append(f"複雑な証拠: {len(conflicting_evidence)}件")
        
        return "\n".join(parts)
    
    def check_for_hallucinations(self, text: str, threshold: float = 0.5) -> Dict[str, Any]:
        """テキスト内のHallucinationを検出"""
        import asyncio
        
        results = asyncio.run(self.verify_text(text))
        
        hallucinations = []
        for result in results:
            if result.status in [
                FactCheckStatus.CONTRADICTED,
                FactCheckStatus.UNVERIFIABLE,
                FactCheckStatus.CONFLICTING,
            ] or result.confidence < threshold:
                hallucinations.append({
                    "claim": result.claim_text,
                    "status": result.status.value,
                    "confidence": result.confidence,
                    "explanation": result.explanation,
                })
        
        return {
            "total_claims": len(results),
            "hallucination_count": len(hallucinations),
            "hallucination_rate": len(hallucinations) / max(1, len(results)),
            "hallucinations": hallucinations,
        }
