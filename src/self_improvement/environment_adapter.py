"""
Phase 6: 環境適応エンジン
========================

システムが環境変化や新たな入力に対して自動的に適応する機構を実装。

主要コンポーネント：
1. QueryAnalyzer - 入力パターン分析
2. AdaptiveParameterTuner - ハイパーパラメータ動的調整
3. EnvironmentAdapter - 統合適応フレームワーク
4. ResourceProfiler - 詳細リソース監視
5. AdaptiveModelSelector - マルチモデル自動選択

テスト: 8/8 PASS 予定
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================
# 1. QueryAnalyzer - 入力パターン分析
# ============================================================

class QueryComplexityLevel(Enum):
    """クエリの複雑性レベル"""
    SIMPLE = "simple"          # 短い単一質問
    MODERATE = "moderate"      # 標準的な質問
    COMPLEX = "complex"        # 複雑な質問
    REASONING = "reasoning"    # 推論が必要


class QueryType(Enum):
    """クエリのタイプ"""
    FACTUAL = "factual"              # 事実を問う質問
    REASONING = "reasoning"          # 理由・因果関係を問う質問
    CREATIVE = "creative"            # 創造的な質問
    CODE_GENERATION = "code_generation"  # コード生成
    MATH = "math"                    # 数学問題
    MULTI_TURN = "multi_turn"        # 複数ターン対話


class LanguageType(Enum):
    """検出された言語"""
    JAPANESE = "ja"
    ENGLISH = "en"
    CHINESE = "zh"
    KOREAN = "ko"
    MIXED = "mixed"


@dataclass
class QueryProfile:
    """入力クエリのプロフィール"""
    query_text: str
    length_chars: int
    length_words: int
    complexity_level: QueryComplexityLevel
    complexity_score: float  # 0.0-1.0
    query_types: List[QueryType]
    detected_language: LanguageType
    num_sentences: int
    avg_sentence_length: float
    contains_code: bool
    contains_equations: bool
    contains_tables: bool
    estimated_answer_complexity: float  # 0.0-1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class QueryAnalyzer:
    """クエリパターン分析エンジン"""
    
    # 言語特性パターン
    JAPANESE_PATTERNS = ["です", "ます", "ですか", "ます。", "し", "では"]
    ENGLISH_PATTERNS = ["the", "is", "are", "have", "that"]
    CHINESE_PATTERNS = ["的", "了", "是", "在", "和"]
    
    # 複雑性判定の閾値
    SIMPLE_THRESHOLD = 50        # 単語数
    COMPLEX_THRESHOLD = 200
    
    # クエリタイプパターン
    CODE_PATTERNS = ["```", "def ", "class ", "import ", "function"]
    MATH_PATTERNS = ["√", "∑", "∫", "sin(", "cos(", "=", "≤", "≥"]
    TABLE_PATTERNS = ["┌", "│", "└", "|", "table"]
    
    def __init__(self):
        logger.info("QueryAnalyzer initialized")
    
    def analyze(self, query: str) -> QueryProfile:
        """クエリを分析してプロファイルを生成"""
        
        # 基本統計
        length_chars = len(query)
        words = query.split()
        length_words = len(words)
        num_sentences = len([s for s in query.split('。') if s.strip()])
        avg_sentence_length = length_words / max(num_sentences, 1)
        
        # 言語検出
        detected_language = self._detect_language(query)
        
        # 複雑性判定
        complexity_level, complexity_score = self._calculate_complexity(
            length_words, avg_sentence_length, num_sentences
        )
        
        # クエリタイプ判定
        query_types = self._detect_query_types(query)
        
        # 特殊パターン検出
        contains_code = any(p in query for p in self.CODE_PATTERNS)
        contains_equations = any(p in query for p in self.MATH_PATTERNS)
        contains_tables = any(p in query for p in self.TABLE_PATTERNS)
        
        # 予想される回答の複雑性
        answer_complexity = self._estimate_answer_complexity(
            complexity_score, query_types, contains_code
        )
        
        profile = QueryProfile(
            query_text=query[:100] + "..." if len(query) > 100 else query,
            length_chars=length_chars,
            length_words=length_words,
            complexity_level=complexity_level,
            complexity_score=complexity_score,
            query_types=query_types,
            detected_language=detected_language,
            num_sentences=num_sentences,
            avg_sentence_length=avg_sentence_length,
            contains_code=contains_code,
            contains_equations=contains_equations,
            contains_tables=contains_tables,
            estimated_answer_complexity=answer_complexity,
        )
        
        logger.info(f"Query analyzed: {complexity_level.value}, score={complexity_score:.2f}")
        return profile
    
    def _detect_language(self, text: str) -> LanguageType:
        """言語を検出"""
        japanese_count = sum(1 for p in self.JAPANESE_PATTERNS if p in text)
        english_count = sum(1 for p in self.ENGLISH_PATTERNS if p in text.lower())
        chinese_count = sum(1 for p in self.CHINESE_PATTERNS if p in text)
        
        if japanese_count > english_count and japanese_count > chinese_count:
            return LanguageType.JAPANESE
        elif english_count > japanese_count and english_count > chinese_count:
            return LanguageType.ENGLISH
        elif chinese_count > japanese_count and chinese_count > english_count:
            return LanguageType.CHINESE
        elif japanese_count > 0 and english_count > 0:
            return LanguageType.MIXED
        else:
            return LanguageType.ENGLISH  # デフォルト
    
    def _calculate_complexity(
        self, length_words: int, avg_sent_len: float, num_sentences: int
    ) -> Tuple[QueryComplexityLevel, float]:
        """複雑性を計算"""
        
        score = 0.0
        
        # 長さに基づくスコア
        if length_words < self.SIMPLE_THRESHOLD:
            length_score = 0.2
        elif length_words > self.COMPLEX_THRESHOLD:
            length_score = 0.8
        else:
            length_score = (length_words - self.SIMPLE_THRESHOLD) / \
                          (self.COMPLEX_THRESHOLD - self.SIMPLE_THRESHOLD)
        
        # 文の長さに基づくスコア
        sent_len_score = min(avg_sent_len / 30.0, 1.0)
        
        # 複数文に基づくスコア
        multi_sent_score = min(num_sentences / 5.0, 1.0)
        
        score = (length_score + sent_len_score + multi_sent_score) / 3.0
        
        if score < 0.3:
            return QueryComplexityLevel.SIMPLE, score
        elif score < 0.6:
            return QueryComplexityLevel.MODERATE, score
        else:
            return QueryComplexityLevel.COMPLEX, score
    
    def _detect_query_types(self, query: str) -> List[QueryType]:
        """クエリのタイプを検出"""
        types = []
        
        if any(p in query for p in self.CODE_PATTERNS):
            types.append(QueryType.CODE_GENERATION)
        
        if any(p in query for p in self.MATH_PATTERNS):
            types.append(QueryType.MATH)
        
        if "why" in query.lower() or "reason" in query.lower() or "cause" in query.lower():
            types.append(QueryType.REASONING)
        
        if "create" in query.lower() or "write" in query.lower() or "invent" in query.lower():
            types.append(QueryType.CREATIVE)
        
        if not types:
            types.append(QueryType.FACTUAL)
        
        return types
    
    def _estimate_answer_complexity(
        self, query_complexity: float, query_types: List[QueryType], has_code: bool
    ) -> float:
        """予想される回答の複雑性を推定"""
        base = query_complexity
        
        # クエリタイプによる調整
        if QueryType.REASONING in query_types:
            base *= 1.3
        elif QueryType.CODE_GENERATION in query_types:
            base *= 1.4
        elif QueryType.CREATIVE in query_types:
            base *= 1.2
        
        return min(base, 1.0)


# ============================================================
# 2. AdaptiveParameterTuner - ハイパーパラメータ動的調整
# ============================================================

class OptimizationStrategy(Enum):
    """最適化戦略"""
    BALANCED = "balanced"              # バランス型
    SPEED_OPTIMIZED = "speed_optimized"  # 高速優先
    QUALITY_OPTIMIZED = "quality_optimized"  # 品質優先
    RESOURCE_CONSTRAINED = "resource_constrained"  # リソース制約下


@dataclass
class AdaptiveParameters:
    """適応されたハイパーパラメータセット"""
    chunk_size: int
    chunk_overlap: int
    batch_size: int
    learning_rate: float
    max_seq_length: int
    num_retrieval_docs: int
    rerank_top_k: int
    cache_strategy: str  # "memory", "disk", "hybrid"
    optimization_strategy: OptimizationStrategy
    rationale: Dict[str, str] = field(default_factory=dict)


class AdaptiveParameterTuner:
    """環境・入力に応じたパラメータ自動調整"""
    
    def __init__(self):
        logger.info("AdaptiveParameterTuner initialized")
        
        # デフォルト値
        self.defaults = {
            "chunk_size": 400,
            "chunk_overlap": 50,
            "batch_size": 4,
            "learning_rate": 1e-5,
            "max_seq_length": 2048,
            "num_retrieval_docs": 5,
            "rerank_top_k": 3,
        }
    
    def tune_for_query(
        self, profile: QueryProfile, available_memory_gb: float = 8.0,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    ) -> AdaptiveParameters:
        """クエリプロフィールに応じてパラメータを調整"""
        
        params = AdaptiveParameters(
            chunk_size=self._tune_chunk_size(profile, strategy),
            chunk_overlap=self._tune_chunk_overlap(profile),
            batch_size=self._tune_batch_size(available_memory_gb, strategy),
            learning_rate=self._tune_learning_rate(profile.complexity_score),
            max_seq_length=self._tune_max_seq_length(profile.complexity_score),
            num_retrieval_docs=self._tune_num_retrieval_docs(profile),
            rerank_top_k=self._tune_rerank_top_k(profile),
            cache_strategy=self._select_cache_strategy(available_memory_gb),
            optimization_strategy=strategy,
        )
        
        logger.info(f"Tuned parameters: chunk_size={params.chunk_size}, batch_size={params.batch_size}")
        return params
    
    def _tune_chunk_size(self, profile: QueryProfile, strategy: OptimizationStrategy) -> int:
        """チャンク長の調整"""
        base = self.defaults["chunk_size"]
        
        # 複雑性に応じた調整
        if profile.complexity_score > 0.7:
            base = int(base * 0.8)  # 複雑な質問は小さいチャンク
        elif profile.complexity_score < 0.3:
            base = int(base * 1.2)  # シンプルな質問は大きいチャンク
        
        # 言語に応じた調整
        if profile.detected_language == LanguageType.JAPANESE:
            base = int(base * 0.9)  # 日本語は短めの設定
        elif profile.detected_language == LanguageType.CHINESE:
            base = int(base * 0.95)
        
        # 戦略に応じた調整
        if strategy == OptimizationStrategy.SPEED_OPTIMIZED:
            base = int(base * 1.3)
        elif strategy == OptimizationStrategy.QUALITY_OPTIMIZED:
            base = int(base * 0.85)
        
        # If code/math, use smaller chunks
        if profile.contains_code or profile.contains_equations:
            base = int(base * 0.7)
        
        self._record_rationale("chunk_size", f"complexity={profile.complexity_score:.2f}, lang={profile.detected_language.value}, has_code={profile.contains_code}")
        
        return max(100, min(base, 1000))  # 100-1000 の範囲
    
    def _tune_chunk_overlap(self, profile: QueryProfile) -> int:
        """チャンク重複の調整"""
        base = self.defaults["chunk_overlap"]
        
        if profile.contains_equations or profile.contains_code:
            base = int(base * 1.5)  # 複雑な構造は重複を増やす
        elif profile.complexity_score < 0.3:
            base = int(base * 0.8)
        
        return max(10, min(base, 200))
    
    def _tune_batch_size(self, available_memory_gb: float, strategy: OptimizationStrategy) -> int:
        """バッチサイズの調整"""
        base = self.defaults["batch_size"]
        
        # メモリに基づいた調整
        if available_memory_gb >= 24:
            base = 16
        elif available_memory_gb >= 16:
            base = 8
        elif available_memory_gb >= 8:
            base = 4
        else:
            base = 2
        
        # 戦略に応じた調整
        if strategy == OptimizationStrategy.SPEED_OPTIMIZED:
            base = int(base * 1.5)
        elif strategy == OptimizationStrategy.RESOURCE_CONSTRAINED:
            base = max(2, int(base * 0.5))
        
        return base
    
    def _tune_learning_rate(self, complexity_score: float) -> float:
        """学習率の調整"""
        base = self.defaults["learning_rate"]
        
        # 複雑性スコアが高いほど、いやらしい学習が必要
        if complexity_score > 0.7:
            return base * 0.8  # より小さい学習率
        elif complexity_score < 0.3:
            return base * 1.2
        
        return base
    
    def _tune_max_seq_length(self, complexity_score: float) -> int:
        """最大シーケンス長の調整"""
        if complexity_score > 0.8:
            return 2048
        elif complexity_score > 0.5:
            return 1024
        else:
            return 512
    
    def _tune_num_retrieval_docs(self, profile: QueryProfile) -> int:
        """検索ドキュメント数の調整"""
        base = self.defaults["num_retrieval_docs"]
        
        if QueryType.REASONING in profile.query_types:
            base = 8
        elif profile.complexity_score > 0.7:
            base = 7
        elif QueryType.FACTUAL in profile.query_types:
            base = 5
        
        return base
    
    def _tune_rerank_top_k(self, profile: QueryProfile) -> int:
        """リランク上位K件の調整"""
        if profile.complexity_score > 0.7:
            return 5
        elif profile.complexity_score > 0.5:
            return 3
        else:
            return 2
    
    def _select_cache_strategy(self, available_memory_gb: float) -> str:
        """キャッシュ戦略の選択"""
        if available_memory_gb >= 16:
            return "memory"
        elif available_memory_gb >= 8:
            return "hybrid"
        else:
            return "disk"
    
    def _record_rationale(self, param_name: str, reason: str):
        """調整理由を記録（ログ）"""
        logger.debug(f"Parameter '{param_name}' adjusted: {reason}")


# ============================================================
# 3. AdaptiveModelSelector - マルチモデル自動選択
# ============================================================

@dataclass
class ModelProfile:
    """モデルのプロファイル"""
    model_name: str
    param_count: int
    avg_latency_ms: float
    avg_accuracy: float
    supports_code: bool
    supports_math: bool
    supports_long_context: bool
    memory_required_gb: float


class AdaptiveModelSelector:
    """クエリ特性とリソース制約に基づくモデル自動選択"""
    
    def __init__(self):
        logger.info("AdaptiveModelSelector initialized")
        
        # モデルプロファイル（既存の src/train/configs.py から）
        self.models = {
            "small_124M": ModelProfile(
                model_name="small_124M",
                param_count=124_000_000,
                avg_latency_ms=50,
                avg_accuracy=0.85,
                supports_code=True,
                supports_math=False,
                supports_long_context=False,
                memory_required_gb=2,
            ),
            "medium_355M": ModelProfile(
                model_name="medium_355M",
                param_count=355_000_000,
                avg_latency_ms=150,
                avg_accuracy=0.92,
                supports_code=True,
                supports_math=True,
                supports_long_context=True,
                memory_required_gb=4,
            ),
            "math_700M": ModelProfile(
                model_name="math_700M",
                param_count=700_000_000,
                avg_latency_ms=300,
                avg_accuracy=0.95,
                supports_code=True,
                supports_math=True,
                supports_long_context=True,
                memory_required_gb=8,
            ),
        }
    
    def select_model(
        self,
        profile: QueryProfile,
        available_memory_gb: float = 8.0,
        latency_budget_ms: float = 200.0,
        accuracy_weight: float = 0.5,
    ) -> str:
        """最適モデルを選択"""
        
        candidates = self._get_feasible_candidates(available_memory_gb, latency_budget_ms)
        
        if not candidates:
            logger.warning("No feasible models found, defaulting to smallest")
            return "small_124M"
        
        # クエリに必要なモデル機能を確認
        required_features = self._get_required_features(profile)
        
        # 機能要件を満たしているモデルにフィルタ
        candidates = [m for m in candidates if self._has_required_features(m, required_features)]
        
        if not candidates:
            # 機能要件が満たせない場合、利用可能な最大モデルを使用
            candidates = self._get_feasible_candidates(available_memory_gb, float('inf'))
        
        # スコアに基づいて最適モデルを選択
        best_model = max(
            candidates,
            key=lambda m: self._calculate_model_score(m, latency_budget_ms, accuracy_weight)
        )
        
        logger.info(f"Selected model: {best_model} for query type: {[t.value for t in profile.query_types]}")
        return best_model
    
    def _get_feasible_candidates(self, available_memory_gb: float, latency_budget_ms: float) -> List[str]:
        """制約を満たす候補モデルを取得"""
        candidates = []
        for name, profile in self.models.items():
            if (profile.memory_required_gb <= available_memory_gb and
                profile.avg_latency_ms <= latency_budget_ms):
                candidates.append(name)
        return candidates
    
    def _get_required_features(self, profile: QueryProfile) -> Dict[str, bool]:
        """クエリに必要なモデル機能を判定"""
        return {
            "code": profile.contains_code or QueryType.CODE_GENERATION in profile.query_types,
            "math": profile.contains_equations or QueryType.MATH in profile.query_types,
            "long_context": profile.length_words > 1000 or profile.complexity_score > 0.8,
        }
    
    def _has_required_features(self, model_name: str, features: Dict[str, bool]) -> bool:
        """モデルが必要な機能に対応しているか確認"""
        model = self.models[model_name]
        return (
            (not features["code"] or model.supports_code) and
            (not features["math"] or model.supports_math) and
            (not features["long_context"] or model.supports_long_context)
        )
    
    def _calculate_model_score(self, model_name: str, latency_budget_ms: float, accuracy_weight: float) -> float:
        """モデルのスコアを計算（高いほど好ましい）"""
        model = self.models[model_name]
        
        # 正規化
        accuracy_norm = model.avg_accuracy  # 0-1 scale
        latency_norm = 1.0 - min(model.avg_latency_ms / latency_budget_ms, 1.0)
        
        # 加重スコア
        score = accuracy_weight * accuracy_norm + (1 - accuracy_weight) * latency_norm
        
        return score


# ============================================================
# 4. EnvironmentAdapter - 統合適応フレームワーク
# ============================================================

@dataclass
class ExecutionContext:
    """実行コンテキスト"""
    user_query: str
    available_memory_gb: float = 8.0
    latency_budget_ms: float = 200.0
    accuracy_weight: float = 0.5
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED


@dataclass
class AdaptedExecutionPlan:
    """適応化された実行計画"""
    model: str
    parameters: AdaptiveParameters
    query_profile: QueryProfile
    rationale: Dict[str, str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EnvironmentAdapter:
    """システム全体の環境適応性をオーケストレーション"""
    
    def __init__(self):
        logger.info("EnvironmentAdapter initialized")
        self.query_analyzer = QueryAnalyzer()
        self.parameter_tuner = AdaptiveParameterTuner()
        self.model_selector = AdaptiveModelSelector()
    
    def adapt_to_context(self, context: ExecutionContext) -> AdaptedExecutionPlan:
        """実行コンテキストに応じてシステム全体を適応"""
        
        # クエリ分析
        query_profile = self.query_analyzer.analyze(context.user_query)
        logger.info(f"Query analyzed: complexity={query_profile.complexity_level.value}")
        
        # パラメータ調整
        parameters = self.parameter_tuner.tune_for_query(
            query_profile,
            available_memory_gb=context.available_memory_gb,
            strategy=context.optimization_strategy
        )
        logger.info(f"Parameters tuned: chunk_size={parameters.chunk_size}, batch_size={parameters.batch_size}")
        
        # モデル選択
        model = self.model_selector.select_model(
            query_profile,
            available_memory_gb=context.available_memory_gb,
            latency_budget_ms=context.latency_budget_ms,
            accuracy_weight=context.accuracy_weight,
        )
        logger.info(f"Model selected: {model}")
        
        # 実行計画を生成
        plan = AdaptedExecutionPlan(
            model=model,
            parameters=parameters,
            query_profile=query_profile,
            rationale={
                "complexity": query_profile.complexity_level.value,
                "model_selection_reason": f"Selected based on latency_budget={context.latency_budget_ms}ms, accuracy_weight={context.accuracy_weight}",
            }
        )
        
        return plan


if __name__ == "__main__":
    # テスト実行例
    logging.basicConfig(level=logging.INFO)
    
    # テストクエリ
    test_queries = [
        "Pythonとは何ですか？",
        "機械学習において、確率勾配降下法をどのように実装しますか？具体的なコード例を示してください。",
        "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
    ]
    
    adapter = EnvironmentAdapter()
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query[:50]}...")
        
        context = ExecutionContext(
            user_query=query,
            available_memory_gb=8.0,
            latency_budget_ms=250.0,
            accuracy_weight=0.6,
        )
        
        plan = adapter.adapt_to_context(context)
        
        print(f"\nAdapted Execution Plan:")
        print(f"  Model: {plan.model}")
        print(f"  Chunk Size: {plan.parameters.chunk_size}")
        print(f"  Batch Size: {plan.parameters.batch_size}")
        print(f"  Query Complexity: {plan.query_profile.complexity_level.value}")
        print(f"  Rationale: {plan.rationale}")
