"""
失敗ケース収集・管理ツール

RAG評価結果から失敗条件を検出し、
再利用可能な失敗ケースとして JSON に保存する。

失敗カテゴリ:
  - hallucination: 根拠のない回答生成
  - wrong_citation: 不正な引用・参照
  - date_error: 日付関連の誤答
  - incomplete_answer: 不完全・部分的な回答
  - contradiction: 矛盾した回答
  - no_answer: 回答未生成
  - poor_relevance: 低い関連性
  - other: その他
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """失敗カテゴリの定義"""
    HALLUCINATION = "hallucination"
    WRONG_CITATION = "wrong_citation"
    DATE_ERROR = "date_error"
    INCOMPLETE_ANSWER = "incomplete_answer"
    CONTRADICTION = "contradiction"
    NO_ANSWER = "no_answer"
    POOR_RELEVANCE = "poor_relevance"
    OTHER = "other"


@dataclass
class FailureCase:
    """
    失敗ケースの定義
    
    Attributes:
        case_id: 一意のケースID（timestamp + hash）
        query: 入力クエリ
        expected_answer: 期待される回答
        actual_answer: 実際の回答
        category: 失敗カテゴリ
        severity: 重要度（0.0-1.0）
        retrieved_documents: 取得されたドキュメント
        search_query: 実行された検索クエリ
        confidence_score: 生成時の信頼度スコア
        reproduction_steps: 再現手順
        root_cause: 根本原因の推測
        tags: カスタムタグ
        timestamp: 検出時刻
        notes: 備考
    """
    case_id: str
    query: str
    expected_answer: str
    actual_answer: str
    category: str  # FailureCategory.value
    severity: float  # 0.0-1.0
    retrieved_documents: List[str] = field(default_factory=list)
    search_query: str = ""
    confidence_score: Optional[float] = None
    reproduction_steps: str = ""
    root_cause: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureCase":
        """辞書から復元"""
        return cls(**data)


class FailureCaseCollector:
    """
    失敗ケースの収集・管理・永続化
    """

    def __init__(self, storage_dir: str = "results/failure_cases"):
        """
        初期化
        
        Args:
            storage_dir: 失敗ケースの保存ディレクトリ
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cases: List[FailureCase] = []
        self._load_existing_cases()

    def _load_existing_cases(self):
        """既存の失敗ケースを読み込む"""
        registry_path = self.storage_dir / "registry.json"
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cases = [FailureCase.from_dict(c) for c in data.get("cases", [])]
                    logger.info(f"Loaded {len(self.cases)} existing failure cases")
            except Exception as e:
                logger.warning(f"Failed to load existing cases: {e}")

    def add_case(
        self,
        query: str,
        expected_answer: str,
        actual_answer: str,
        category: FailureCategory,
        severity: float = 0.5,
        retrieved_documents: Optional[List[str]] = None,
        search_query: str = "",
        confidence_score: Optional[float] = None,
        reproduction_steps: str = "",
        root_cause: str = "",
        tags: Optional[List[str]] = None,
        notes: str = "",
    ) -> FailureCase:
        """
        新しい失敗ケースを追加
        
        Args:
            query: 入力クエリ
            expected_answer: 期待される回答
            actual_answer: 実際の回答
            category: 失敗カテゴリ
            severity: 重要度（0.0-1.0）
            retrieved_documents: 取得されたドキュメント
            search_query: 実行された検索クエリ
            confidence_score: 生成時の信頼度スコア
            reproduction_steps: 再現手順
            root_cause: 根本原因の推測
            tags: カスタムタグ
            notes: 備考
            
        Returns:
            追加された FailureCase
        """
        # ケースID生成（timestamp + hash）
        timestamp = datetime.now().isoformat()
        case_hash = hash(f"{query}:{expected_answer}:{timestamp}") % 10000
        case_id = f"failure_{int(datetime.now().timestamp())}_{case_hash:04d}"

        case = FailureCase(
            case_id=case_id,
            query=query,
            expected_answer=expected_answer,
            actual_answer=actual_answer,
            category=category.value,
            severity=max(0.0, min(1.0, severity)),
            retrieved_documents=retrieved_documents or [],
            search_query=search_query,
            confidence_score=confidence_score,
            reproduction_steps=reproduction_steps,
            root_cause=root_cause,
            tags=tags or [],
            timestamp=timestamp,
            notes=notes,
        )

        self.cases.append(case)
        logger.info(f"Added failure case: {case_id} (category={category.value})")
        return case

    def detect_from_evaluation_result(
        self,
        query: str,
        expected_answer: str,
        actual_answer: str,
        retrieved_documents: Optional[List[str]] = None,
        confidence_score: Optional[float] = None,
        search_query: str = "",
    ) -> Optional[FailureCase]:
        """
        評価結果から失敗を自動検出して追加
        
        失敗検出ルール:
        - 回答が空またはNone → NO_ANSWER
        - 信頼度スコアが低い（<0.3）→ POOR_RELEVANCE
        - 実際の回答と期待の回答が大きく異なる → HALLUCINATION or WRONG_CITATION
        
        Args:
            query: 入力クエリ
            expected_answer: 期待される回答
            actual_answer: 実際の回答
            retrieved_documents: 取得されたドキュメント
            confidence_score: 生成時の信頼度スコア
            search_query: 実行された検索クエリ
            
        Returns:
            検出された FailureCase、失敗なし場合は None
        """
        # 空回答の検出
        if not actual_answer or actual_answer.strip() == "":
            return self.add_case(
                query=query,
                expected_answer=expected_answer,
                actual_answer=actual_answer or "[NO ANSWER]",
                category=FailureCategory.NO_ANSWER,
                severity=1.0,
                retrieved_documents=retrieved_documents,
                search_query=search_query,
                confidence_score=confidence_score or 0.0,
            )

        # 信頼度スコアが低い場合
        if confidence_score is not None and confidence_score < 0.3:
            return self.add_case(
                query=query,
                expected_answer=expected_answer,
                actual_answer=actual_answer,
                category=FailureCategory.POOR_RELEVANCE,
                severity=1.0 - confidence_score,
                retrieved_documents=retrieved_documents,
                search_query=search_query,
                confidence_score=confidence_score,
            )

        # 日付関連キーワード検出
        date_keywords = ["年", "月", "日", "今年", "去年", "来年", "時点", "現在"]
        if any(kw in query for kw in date_keywords):
            # 期待値と実際の値が一致しない場合
            if expected_answer not in actual_answer:
                return self.add_case(
                    query=query,
                    expected_answer=expected_answer,
                    actual_answer=actual_answer,
                    category=FailureCategory.DATE_ERROR,
                    severity=0.9,
                    retrieved_documents=retrieved_documents,
                    search_query=search_query,
                    confidence_score=confidence_score,
                    tags=["date-sensitive"],
                )

        # 期待値と実際の値の類似度が低い場合
        # ただし、期待値が実際の値の部分文字列として含まれている場合は失敗とみなさない
        if expected_answer.lower() not in actual_answer.lower():
            if self._similarity(expected_answer, actual_answer) < 0.3:
                return self.add_case(
                    query=query,
                    expected_answer=expected_answer,
                    actual_answer=actual_answer,
                    category=FailureCategory.HALLUCINATION,
                    severity=0.7,
                    retrieved_documents=retrieved_documents,
                    search_query=search_query,
                    confidence_score=confidence_score,
                    root_cause="Generated answer significantly differs from expected",
                )

        return None

    def get_cases_by_category(self, category: FailureCategory) -> List[FailureCase]:
        """指定カテゴリの失敗ケース一覧を取得"""
        return [c for c in self.cases if c.category == category.value]

    def get_cases_by_severity(
        self, min_severity: float = 0.0, max_severity: float = 1.0
    ) -> List[FailureCase]:
        """重要度範囲内の失敗ケース一覧を取得"""
        return [
            c
            for c in self.cases
            if min_severity <= c.severity <= max_severity
        ]

    def get_high_priority_cases(self, top_n: int = 10) -> List[FailureCase]:
        """重要度が高いケースをランク順に取得"""
        sorted_cases = sorted(self.cases, key=lambda c: c.severity, reverse=True)
        return sorted_cases[:top_n]

    def save(self):
        """失敗ケースを永続化"""
        registry_path = self.storage_dir / "registry.json"
        data = {
            "total_cases": len(self.cases),
            "last_updated": datetime.now().isoformat(),
            "cases": [c.to_dict() for c in self.cases],
        }

        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.cases)} failure cases to {registry_path}")
        except Exception as e:
            logger.error(f"Failed to save failure cases: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """失敗ケースの統計情報を取得"""
        if not self.cases:
            return {
                "total_cases": 0,
                "categories": {},
                "severity_distribution": {},
                "top_tags": [],
            }

        # カテゴリ別集計
        category_counts = {}
        for case in self.cases:
            category_counts[case.category] = category_counts.get(case.category, 0) + 1

        # 重要度分布
        severity_bins = {
            "critical": len([c for c in self.cases if c.severity >= 0.8]),
            "high": len([c for c in self.cases if 0.6 <= c.severity < 0.8]),
            "medium": len([c for c in self.cases if 0.4 <= c.severity < 0.6]),
            "low": len([c for c in self.cases if c.severity < 0.4]),
        }

        # タグ集計
        tag_counts = {}
        for case in self.cases:
            for tag in case.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_cases": len(self.cases),
            "categories": category_counts,
            "severity_distribution": severity_bins,
            "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        }

    @staticmethod
    def _similarity(str1: str, str2: str) -> float:
        """
        2つの文字列の類似度を計算（簡易版）
        
        Returns:
            0.0-1.0 の類似度スコア
        """
        # 両方が空の場合
        if not str1 and not str2:
            return 1.0

        # どちらかが空の場合
        if not str1 or not str2:
            return 0.0

        # 単語の重複度
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0


# CLI用の便利関数
def collect_failures_from_benchmark(
    benchmark_result_path: str, storage_dir: str = "results/failure_cases"
) -> Dict[str, Any]:
    """
    ベンチマーク結果から失敗ケースを自動収集
    
    Args:
        benchmark_result_path: ベンチマーク結果JSONのパス
        storage_dir: 失敗ケース保存ディレクトリ
        
    Returns:
        処理結果サマリー
    """
    collector = FailureCaseCollector(storage_dir)

    try:
        with open(benchmark_result_path, "r", encoding="utf-8") as f:
            benchmark_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load benchmark result: {e}")
        return {"success": False, "error": str(e)}

    samples = benchmark_data.get("samples", [])
    detected_count = 0
    skipped_count = 0

    for sample in samples:
        try:
            query = sample.get("query", "")
            expected = sample.get("expected_output", "")
            actual = sample.get("generated_answer", "")

            if not query or not expected:
                skipped_count += 1
                continue

            case = collector.detect_from_evaluation_result(
                query=query,
                expected_answer=expected,
                actual_answer=actual,
                retrieved_documents=sample.get("retrieved_documents", []),
                confidence_score=sample.get("confidence_score"),
                search_query=sample.get("search_query", ""),
            )

            if case:
                detected_count += 1

        except Exception as e:
            logger.warning(f"Error processing sample: {e}")
            skipped_count += 1

    collector.save()
    stats = collector.get_statistics()

    return {
        "success": True,
        "detected_failures": detected_count,
        "skipped_samples": skipped_count,
        "total_cases": len(collector.cases),
        "statistics": stats,
    }
