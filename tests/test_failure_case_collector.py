"""
失敗ケース収集ツール（FailureCaseCollector）のテスト
"""

import json
import pytest
from pathlib import Path
from src.evaluation.failure_case_collector import (
    FailureCase,
    FailureCategory,
    FailureCaseCollector,
    collect_failures_from_benchmark,
)


class TestFailureCase:
    """FailureCaseクラスのテスト"""

    def test_failure_case_creation(self):
        """FailureCaseが正しく作成されるか"""
        case = FailureCase(
            case_id="test_001",
            query="What is AI?",
            expected_answer="Artificial Intelligence",
            actual_answer="Application Interface",
            category=FailureCategory.HALLUCINATION.value,
            severity=0.8,
            tags=["hallucination", "definition"],
        )

        assert case.case_id == "test_001"
        assert case.query == "What is AI?"
        assert case.severity == 0.8
        assert len(case.tags) == 2

    def test_failure_case_to_dict(self):
        """FailureCaseが辞書に変換されるか"""
        case = FailureCase(
            case_id="test_002",
            query="Test query",
            expected_answer="Expected",
            actual_answer="Actual",
            category=FailureCategory.WRONG_CITATION.value,
            severity=0.6,
        )

        case_dict = case.to_dict()

        assert isinstance(case_dict, dict)
        assert case_dict["case_id"] == "test_002"
        assert case_dict["category"] == "wrong_citation"

    def test_failure_case_from_dict(self):
        """辞書からFailureCaseが復元されるか"""
        data = {
            "case_id": "test_003",
            "query": "Query",
            "expected_answer": "Expected",
            "actual_answer": "Actual",
            "category": "date_error",
            "severity": 0.9,
            "retrieved_documents": ["doc1", "doc2"],
            "search_query": "search",
            "confidence_score": 0.5,
            "reproduction_steps": "steps",
            "root_cause": "cause",
            "tags": ["date"],
            "timestamp": "2026-06-01T12:00:00",
            "notes": "note",
        }

        case = FailureCase.from_dict(data)

        assert case.case_id == "test_003"
        assert case.category == "date_error"
        assert case.severity == 0.9
        assert len(case.tags) == 1


class TestFailureCaseCollector:
    """FailureCaseCollectorクラスのテスト"""

    @pytest.fixture
    def collector(self, tmp_path):
        """テスト用のコレクターインスタンス"""
        storage_dir = str(tmp_path / "failure_cases")
        return FailureCaseCollector(storage_dir=storage_dir)

    def test_collector_initialization(self, collector):
        """コレクターが正しく初期化されるか"""
        assert collector.storage_dir.exists()
        assert isinstance(collector.cases, list)
        assert len(collector.cases) == 0

    def test_add_case(self, collector):
        """ケースが追加されるか"""
        case = collector.add_case(
            query="What is Python?",
            expected_answer="A programming language",
            actual_answer="A snake",
            category=FailureCategory.HALLUCINATION,
            severity=0.7,
        )

        assert case is not None
        assert len(collector.cases) == 1
        assert collector.cases[0].query == "What is Python?"

    def test_add_multiple_cases(self, collector):
        """複数のケースが追加されるか"""
        collector.add_case(
            query="Query1",
            expected_answer="Expected1",
            actual_answer="Actual1",
            category=FailureCategory.HALLUCINATION,
        )
        collector.add_case(
            query="Query2",
            expected_answer="Expected2",
            actual_answer="Actual2",
            category=FailureCategory.WRONG_CITATION,
        )

        assert len(collector.cases) == 2

    def test_detect_empty_answer(self, collector):
        """空回答を検出するか"""
        case = collector.detect_from_evaluation_result(
            query="Question?",
            expected_answer="Expected answer",
            actual_answer="",  # 空回答
        )

        assert case is not None
        assert case.category == FailureCategory.NO_ANSWER.value
        assert case.severity == 1.0

    def test_detect_low_confidence(self, collector):
        """低信頼度を検出するか"""
        case = collector.detect_from_evaluation_result(
            query="Question?",
            expected_answer="Expected",
            actual_answer="Actual answer",
            confidence_score=0.2,  # 低い信頼度
        )

        assert case is not None
        assert case.category == FailureCategory.POOR_RELEVANCE.value

    def test_detect_date_error(self, collector):
        """日付エラーを検出するか"""
        case = collector.detect_from_evaluation_result(
            query="2026年の日本の総人口は？",
            expected_answer="125,000,000人",
            actual_answer="100,000,000人",  # 不一致
        )

        assert case is not None
        assert case.category == FailureCategory.DATE_ERROR.value
        assert "date-sensitive" in case.tags

    def test_detect_hallucination(self, collector):
        """ハルシネーションを検出するか"""
        case = collector.detect_from_evaluation_result(
            query="Who is the president of France?",
            expected_answer="Emmanuel Macron",
            actual_answer="Napoleon Bonaparte",  # 大きく異なる
            confidence_score=0.8,
        )

        assert case is not None
        assert case.category == FailureCategory.HALLUCINATION.value

    def test_no_detection_for_good_answer(self, collector):
        """良い回答を失敗と判定しないか"""
        case = collector.detect_from_evaluation_result(
            query="What is 2+2?",
            expected_answer="4",
            actual_answer="The sum of 2 and 2 is 4",
            confidence_score=0.95,
        )

        # 期待値が実際の値に含まれれば検出されない
        assert case is None

    def test_get_cases_by_category(self, collector):
        """カテゴリ別検索ができるか"""
        collector.add_case(
            query="Q1",
            expected_answer="E1",
            actual_answer="A1",
            category=FailureCategory.HALLUCINATION,
        )
        collector.add_case(
            query="Q2",
            expected_answer="E2",
            actual_answer="A2",
            category=FailureCategory.WRONG_CITATION,
        )
        collector.add_case(
            query="Q3",
            expected_answer="E3",
            actual_answer="A3",
            category=FailureCategory.HALLUCINATION,
        )

        hallucination_cases = collector.get_cases_by_category(
            FailureCategory.HALLUCINATION
        )
        assert len(hallucination_cases) == 2

    def test_get_cases_by_severity(self, collector):
        """重要度範囲での検索ができるか"""
        collector.add_case(
            query="Q1",
            expected_answer="E1",
            actual_answer="A1",
            category=FailureCategory.HALLUCINATION,
            severity=0.2,
        )
        collector.add_case(
            query="Q2",
            expected_answer="E2",
            actual_answer="A2",
            category=FailureCategory.HALLUCINATION,
            severity=0.7,
        )
        collector.add_case(
            query="Q3",
            expected_answer="E3",
            actual_answer="A3",
            category=FailureCategory.HALLUCINATION,
            severity=0.9,
        )

        high_severity = collector.get_cases_by_severity(min_severity=0.6)
        assert len(high_severity) == 2

    def test_get_high_priority_cases(self, collector):
        """優先度が高いケース取得ができるか"""
        for i, severity in enumerate([0.2, 0.5, 0.8, 0.95, 0.3, 0.9]):
            collector.add_case(
                query=f"Q{i}",
                expected_answer=f"E{i}",
                actual_answer=f"A{i}",
                category=FailureCategory.HALLUCINATION,
                severity=severity,
            )

        top_cases = collector.get_high_priority_cases(top_n=3)
        assert len(top_cases) == 3
        assert top_cases[0].severity >= top_cases[1].severity >= top_cases[2].severity

    def test_save_and_load(self, collector):
        """保存と読み込みができるか"""
        collector.add_case(
            query="Question",
            expected_answer="Expected",
            actual_answer="Actual",
            category=FailureCategory.HALLUCINATION,
            severity=0.8,
            tags=["test"],
        )

        collector.save()

        # 新しいコレクターで読み込む
        new_collector = FailureCaseCollector(storage_dir=str(collector.storage_dir))
        assert len(new_collector.cases) == 1
        assert new_collector.cases[0].query == "Question"
        assert new_collector.cases[0].tags == ["test"]

    def test_get_statistics(self, collector):
        """統計情報が正しく取得できるか"""
        collector.add_case(
            query="Q1",
            expected_answer="E1",
            actual_answer="A1",
            category=FailureCategory.HALLUCINATION,
            severity=0.9,
            tags=["halluc"],
        )
        collector.add_case(
            query="Q2",
            expected_answer="E2",
            actual_answer="A2",
            category=FailureCategory.WRONG_CITATION,
            severity=0.5,
            tags=["citation", "halluc"],
        )

        stats = collector.get_statistics()

        assert stats["total_cases"] == 2
        assert "hallucination" in stats["categories"]
        assert stats["categories"]["hallucination"] == 1
        assert stats["severity_distribution"]["critical"] == 1  # 0.9 >= 0.8
        assert stats["severity_distribution"]["medium"] == 1  # 0.5 in [0.4, 0.6)

    def test_get_statistics_empty(self, collector):
        """空のコレクターで統計情報が取得できるか"""
        stats = collector.get_statistics()

        assert stats["total_cases"] == 0
        assert stats["categories"] == {}
        assert stats["top_tags"] == []

    def test_similarity_calculation(self):
        """文字列類似度の計算が正しいか"""
        # 完全一致
        sim = FailureCaseCollector._similarity("hello world", "hello world")
        assert sim == 1.0

        # 部分一致
        sim = FailureCaseCollector._similarity("hello world", "hello there")
        assert 0 < sim < 1

        # 完全不一致
        sim = FailureCaseCollector._similarity("hello", "goodbye")
        assert sim == 0.0

        # 空文字列
        sim = FailureCaseCollector._similarity("", "")
        assert sim == 1.0

        sim = FailureCaseCollector._similarity("hello", "")
        assert sim == 0.0


class TestCollectFailuresFromBenchmark:
    """collect_failures_from_benchmark関数のテスト"""

    def test_collect_from_benchmark_file(self, tmp_path):
        """ベンチマークファイルから失敗ケースを収集できるか"""
        # テスト用のベンチマーク結果を作成
        benchmark_data = {
            "samples": [
                {
                    "query": "What is AI?",
                    "expected_output": "Artificial Intelligence",
                    "generated_answer": "Application Interface",  # 誤答
                    "retrieved_documents": ["doc1"],
                    "confidence_score": 0.2,
                },
                {
                    "query": "2+2=?",
                    "expected_output": "4",
                    "generated_answer": "The answer is 4",
                    "retrieved_documents": ["doc2"],
                    "confidence_score": 0.95,
                },
                {
                    "query": "What is X?",
                    "expected_output": "Expected",
                    "generated_answer": "",  # 空回答
                    "retrieved_documents": [],
                    "confidence_score": 0.0,
                },
            ]
        }

        benchmark_file = tmp_path / "benchmark.json"
        with open(benchmark_file, "w", encoding="utf-8") as f:
            json.dump(benchmark_data, f)

        # 収集実行
        result = collect_failures_from_benchmark(
            str(benchmark_file), storage_dir=str(tmp_path / "failures")
        )

        assert result["success"] is True
        assert result["detected_failures"] >= 1  # 少なくとも1つ失敗を検出
        assert result["total_cases"] >= 1

    def test_collect_handles_missing_file(self, tmp_path):
        """ファイルが存在しない場合の処理"""
        result = collect_failures_from_benchmark(
            str(tmp_path / "nonexistent.json"),
            storage_dir=str(tmp_path / "failures"),
        )

        assert result["success"] is False
        assert "error" in result

    def test_collect_handles_malformed_data(self, tmp_path):
        """不正な形式のデータ処理"""
        benchmark_file = tmp_path / "benchmark.json"
        with open(benchmark_file, "w", encoding="utf-8") as f:
            f.write("not valid json")

        result = collect_failures_from_benchmark(str(benchmark_file))

        assert result["success"] is False


class TestFailureCaseIntegration:
    """統合テスト"""

    def test_end_to_end_failure_case_workflow(self, tmp_path):
        """エンドツーエンドのワークフロー"""
        storage_dir = str(tmp_path / "failures")
        collector = FailureCaseCollector(storage_dir=storage_dir)

        # 複数の失敗ケースを追加
        for i in range(5):
            collector.add_case(
                query=f"Question {i}",
                expected_answer=f"Expected {i}",
                actual_answer=f"Wrong {i}",
                category=FailureCategory.HALLUCINATION,
                severity=0.5 + (i * 0.1),
                tags=["test", f"group-{i % 2}"],
            )

        # 自動検出
        case = collector.detect_from_evaluation_result(
            query="2026年の日本GDP",
            expected_answer="5000兆円",
            actual_answer="1000兆円",
        )
        assert case is not None

        # 保存
        collector.save()
        registry_file = Path(storage_dir) / "registry.json"
        assert registry_file.exists()

        # 新しいインスタンスで読み込む
        loaded_collector = FailureCaseCollector(storage_dir=storage_dir)
        assert len(loaded_collector.cases) > 0

        # 統計情報取得
        stats = loaded_collector.get_statistics()
        assert stats["total_cases"] > 0
        assert "hallucination" in stats["categories"]
