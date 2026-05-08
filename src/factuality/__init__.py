"""
事実性検証エンジン
Phase 12 Task 2

ファクトチェック、Hallucination検出、信頼度スコアリング
目標: Hallucination削減 >30%, 正確性向上 90%+
"""

from .fact_verifier import FactVerifier, FactCheckResult
from .confidence_scorer import ConfidenceScorer
from .knowledge_base_mapper import KnowledgeBaseMapper
from .hallucination_detector import HallucinationDetector

__all__ = [
    'FactVerifier',
    'FactCheckResult',
    'ConfidenceScorer',
    'KnowledgeBaseMapper',
    'HallucinationDetector',
]
