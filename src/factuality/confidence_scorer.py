"""
信頼度スコアリングエンジン
複数要因に基づくスコア計算
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)


class SourceReliability(Enum):
    """ソース信頼度レベル"""
    VERY_HIGH = (0.95, "学術論文、公式政府サイト")
    HIGH = (0.85, "Wikipedia、認定メディア")
    MEDIUM = (0.65, "ニュース記事、オンラインフォーラム")
    LOW = (0.40, "ブログ、ソーシャルメディア")
    VERY_LOW = (0.15, "匿名投稿、不明なソース")


@dataclass
class ScoreComponent:
    """スコア構成要素"""
    name: str
    weight: float
    value: float
    contribution: float = 0.0
    
    def compute_contribution(self) -> float:
        """加重スコア寄与度を計算"""
        self.contribution = self.weight * self.value
        return self.contribution


class SourceCredibilityScorer:
    """ソース信頼度スコアリング"""
    
    # ドメイン別の信頼度マッピング
    DOMAIN_SCORES = {
        "wikipedia.org": 0.85,
        "gov": 0.9,
        ".edu": 0.9,
        "nature.com": 0.95,
        "science.org": 0.95,
        "reuters.com": 0.85,
        "bbc.com": 0.85,
        "ap.org": 0.85,
        "medium.com": 0.5,
        "reddit.com": 0.3,
        "twitter.com": 0.25,
    }
    
    @classmethod
    def score_source(cls, source_name: str, url: Optional[str] = None) -> float:
        """ソースの信頼度をスコア付け (0-1)"""
        
        # URLベースのスコア
        if url:
            url_lower = url.lower()
            for domain, score in cls.DOMAIN_SCORES.items():
                if domain in url_lower:
                    return score
        
        # ソース名ベースのマッピング
        source_lower = source_name.lower()
        if "wikipedia" in source_lower:
            return 0.85
        elif "government" in source_lower or "official" in source_lower:
            return 0.9
        elif "news" in source_lower or "press" in source_lower:
            return 0.8
        elif "academic" in source_lower or "research" in source_lower:
            return 0.92
        elif "blog" in source_lower or "personal" in source_lower:
            return 0.4
        elif "social" in source_lower:
            return 0.25
        else:
            return 0.5  # デフォルト


class EvidenceMatchScorer:
    """エビデンス・クレイム一致度スコアリング"""
    
    @staticmethod
    def compute_match_score(
        claim_text: str,
        evidence_text: str,
        keywords: Optional[List[str]] = None,
    ) -> float:
        """
        エビデンスがクレイムとどの程度マッチするかを計算
        スコア: 0-1 (1 = 完全一致)
        """
        
        # 長さが大きく異なる場合ペナルティ
        length_score = min(len(evidence_text), len(claim_text)) / max(len(evidence_text), len(claim_text))
        
        # キーワードオーバーラップ
        claim_words = set(claim_text.lower().split())
        evidence_words = set(evidence_text.lower().split())
        
        overlap = claim_words & evidence_words
        union = claim_words | evidence_words
        
        overlap_score = len(overlap) / max(1, len(union))
        
        # キーワード一致スコア
        keyword_score = 0.0
        if keywords:
            keyword_matches = sum(1 for kw in keywords if kw.lower() in evidence_text.lower())
            keyword_score = keyword_matches / len(keywords) if keywords else 0.0
        
        # 複合スコア
        match_score = (length_score * 0.2 + overlap_score * 0.4 + keyword_score * 0.4)
        
        return max(0.0, min(1.0, match_score))
    
    @staticmethod
    def compute_contradiction_level(
        claim_text: str,
        evidence_text: str,
    ) -> float:
        """
        エビデンスとクレイムの矛盾度を計算
        スコア: 0-1 (1 = 完全矛盾)
        """
        
        contradiction_keywords = {
            "not": 0.7,
            "no": 0.7,
            "never": 0.9,
            "false": 0.95,
            "contradiction": 0.95,
            "denies": 0.85,
            "contrary": 0.8,
            "opposite": 0.85,
            "however": 0.5,
            "but": 0.4,
        }
        
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()
        
        # 矛盾キーワードの検出
        contradiction_score = 0.0
        for keyword, weight in contradiction_keywords.items():
            if keyword in evidence_lower and keyword not in claim_lower:
                contradiction_score = max(contradiction_score, weight)
        
        # エビデンスのトーンが違う場合のペナルティ
        # （この実装では簡略化）
        
        return max(0.0, min(1.0, contradiction_score))


class RecencyScorer:
    """情報の新鮮度スコアリング"""
    
    @staticmethod
    def score_by_date(publication_date: Optional[str], current_year: int = 2026) -> float:
        """
        発行日から新鮮度スコアを計算
        スコア: 0-1 (1 = 最新)
        """
        
        if not publication_date:
            return 0.5  # 不明な場合は中程度
        
        try:
            # YYYYフォーマットを想定
            year = int(publication_date[:4])
            age_years = current_year - year
            
            # 情報の鮮度スコア（指数関数）
            # 1年で0.95, 2年で0.90, 5年で0.74
            recency_score = math.exp(-0.05 * age_years)
            
            return max(0.0, min(1.0, recency_score))
        except (ValueError, IndexError):
            return 0.5


class ConfidenceScorer:
    """総合信頼度スコアリング"""
    
    def __init__(self):
        self.source_scorer = SourceCredibilityScorer()
        self.match_scorer = EvidenceMatchScorer()
        self.recency_scorer = RecencyScorer()
        
        # スコア構成要素のウェイト
        self.weights = {
            "source_credibility": 0.3,
            "match_quality": 0.35,
            "recency": 0.15,
            "evidence_count": 0.1,
            "consensus": 0.1,
        }
    
    def compute_claim_confidence(
        self,
        claim_text: str,
        evidence_list: List[Dict],
        current_year: int = 2026,
    ) -> Tuple[float, Dict[str, ScoreComponent]]:
        """
        クレイムに対する総合信頼度スコアを計算
        
        Args:
            claim_text: 検証するクレイムテキスト
            evidence_list: エビデンスのリスト [{
                'text': str,
                'source': str,
                'url': str (optional),
                'date': str (optional, YYYY-MM-DD format)
            }]
            current_year: 現在の年（新鮮度計算用）
        
        Returns:
            (総合スコア, スコア構成要素の詳細)
        """
        
        components = {}
        
        if not evidence_list:
            return 0.5, {}
        
        # 1. ソース信頼度スコア
        source_scores = []
        for evidence in evidence_list:
            score = self.source_scorer.score_source(
                evidence.get("source", "Unknown"),
                evidence.get("url"),
            )
            source_scores.append(score)
        
        avg_source_score = sum(source_scores) / len(source_scores) if source_scores else 0.5
        components["source_credibility"] = ScoreComponent(
            name="ソース信頼度",
            weight=self.weights["source_credibility"],
            value=avg_source_score,
        )
        
        # 2. マッチ品質スコア
        match_scores = []
        keywords = claim_text.lower().split()[:5]
        for evidence in evidence_list:
            score = self.match_scorer.compute_match_score(
                claim_text,
                evidence.get("text", ""),
                keywords,
            )
            match_scores.append(score)
        
        avg_match_score = sum(match_scores) / len(match_scores) if match_scores else 0.5
        components["match_quality"] = ScoreComponent(
            name="エビデンス一致度",
            weight=self.weights["match_quality"],
            value=avg_match_score,
        )
        
        # 3. 新鮮度スコア
        recency_scores = []
        for evidence in evidence_list:
            score = self.recency_scorer.score_by_date(
                evidence.get("date"),
                current_year,
            )
            recency_scores.append(score)
        
        avg_recency_score = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5
        components["recency"] = ScoreComponent(
            name="情報新鮮度",
            weight=self.weights["recency"],
            value=avg_recency_score,
        )
        
        # 4. エビデンス数スコア
        evidence_count_score = min(1.0, len(evidence_list) / 5.0)  # 5つ以上で満点
        components["evidence_count"] = ScoreComponent(
            name="エビデンス数",
            weight=self.weights["evidence_count"],
            value=evidence_count_score,
        )
        
        # 5. コンセンサススコア（複数のエビデンスが一致しているか）
        consensus_score = 0.7 if len(evidence_list) > 1 else 0.5
        if len(evidence_list) >= 3:
            consensus_score = 0.9
        components["consensus"] = ScoreComponent(
            name="コンセンサス",
            weight=self.weights["consensus"],
            value=consensus_score,
        )
        
        # 総合スコア計算
        total_score = 0.0
        for component in components.values():
            contribution = component.compute_contribution()
            total_score += contribution
        
        # 重みの合計で正規化
        total_weight = sum(self.weights.values())
        total_score = total_score / total_weight if total_weight > 0 else 0.5
        
        return max(0.0, min(1.0, total_score)), components
    
    def get_confidence_label(self, score: float) -> str:
        """信頼度スコアをラベルに変換"""
        if score >= 0.9:
            return "Very High"
        elif score >= 0.7:
            return "High"
        elif score >= 0.5:
            return "Medium"
        elif score >= 0.3:
            return "Low"
        else:
            return "Very Low"


class CrossSourceAgreement:
    """複数ソース間の合意度を計算"""
    
    @staticmethod
    def compute_agreement_score(
        source_positions: Dict[str, str],
    ) -> float:
        """
        複数のソースがどの程度同じポジションを取っているかを計算
        
        Args:
            source_positions: {source_name: "supports" | "contradicts" | "neutral"}
        
        Returns:
            合意度スコア (0-1)
        """
        
        if not source_positions:
            return 0.5
        
        positions = list(source_positions.values())
        
        # 最も一般的なポジション
        from collections import Counter
        position_counts = Counter(positions)
        max_count = position_counts.most_common(1)[0][1]
        
        # 合意度 = 最多ポジション数 / 総ソース数
        agreement_score = max_count / len(positions)
        
        return agreement_score
