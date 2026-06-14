"""
失敗ケース収集 CLI ツール（tools/failure_case_cli.py）のテスト
"""

import json
import subprocess
import pytest
from pathlib import Path
import sys


@pytest.fixture
def benchmark_json(tmp_path):
    """テスト用ベンチマークJSONファイル"""
    benchmark_data = {
        "samples": [
            {
                "query": "What is AI?",
                "expected_output": "Artificial Intelligence",
                "generated_answer": "Application Interface",
                "retrieved_documents": ["doc1"],
                "confidence_score": 0.2,
            },
            {
                "query": "What is 2+2?",
                "expected_output": "4",
                "generated_answer": "The answer is 4",
                "retrieved_documents": ["doc2"],
                "confidence_score": 0.95,
            },
            {
                "query": "What is X?",
                "expected_output": "Expected X",
                "generated_answer": "",
                "retrieved_documents": [],
                "confidence_score": 0.0,
            },
        ]
    }

    benchmark_file = tmp_path / "benchmark.json"
    with open(benchmark_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f)

    return str(benchmark_file)


def run_cli_command(args, cwd=None):
    """CLI コマンドを実行"""
    cmd = [
        sys.executable,
        "tools/failure_case_cli.py",
    ] + args

    result = subprocess.run(
        cmd,
        cwd=cwd or Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    return result


class TestFailureCaseCLI:
    """失敗ケース収集 CLI のテスト"""

    def test_cli_help(self):
        """ヘルプ表示"""
        result = run_cli_command(["--help"])
        assert result.returncode == 0
        assert "Failure Case Collector CLI Tool" in result.stdout

    def test_cli_collect_from_benchmark(self, benchmark_json, tmp_path):
        """ベンチマークから収集"""
        storage_dir = tmp_path / "failures"

        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        assert result.returncode == 0
        assert "✅ Collection completed" in result.stdout or "Collection completed" in result.stdout
        assert "detected_failures" in result.stdout.lower() or "Detected failures" in result.stdout

    def test_cli_stats(self, benchmark_json, tmp_path):
        """統計情報表示"""
        storage_dir = tmp_path / "failures"

        # 先に収集
        run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        # 統計表示
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "stats",
        ])

        assert result.returncode == 0
        assert "Failure Case Statistics" in result.stdout or "Total Cases" in result.stdout

    def test_cli_list(self, benchmark_json, tmp_path):
        """ケース一覧表示"""
        storage_dir = tmp_path / "failures"

        # 先に収集
        run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        # 一覧表示
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "list",
        ])

        assert result.returncode == 0
        # テーブル形式で出力される
        assert "Case ID" in result.stdout or "Query" in result.stdout

    def test_cli_list_with_category_filter(self, benchmark_json, tmp_path):
        """カテゴリフィルター付き一覧表示"""
        storage_dir = tmp_path / "failures"

        # 先に収集
        run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        # hallucination カテゴリでフィルター
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "list",
            "--category",
            "hallucination",
        ])

        assert result.returncode == 0

    def test_cli_export_csv(self, benchmark_json, tmp_path):
        """CSV エクスポート"""
        storage_dir = tmp_path / "failures"
        output_csv = tmp_path / "output.csv"

        # 先に収集
        run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        # エクスポート
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "export",
            str(output_csv),
        ])

        assert result.returncode == 0
        assert output_csv.exists()

        # CSV の内容確認
        with open(output_csv, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) > 1  # ヘッダー + データ
            assert "case_id" in lines[0]
            assert "query" in lines[0]

    def test_cli_export_empty_storage(self, tmp_path):
        """空のストレージでエクスポート"""
        storage_dir = tmp_path / "failures"
        storage_dir.mkdir(parents=True)
        output_csv = tmp_path / "output.csv"

        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "export",
            str(output_csv),
        ])

        assert result.returncode == 1
        assert "No failure cases" in result.stdout

    def test_cli_stats_empty_storage(self, tmp_path):
        """空のストレージで統計表示"""
        storage_dir = tmp_path / "failures"
        storage_dir.mkdir(parents=True)

        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "stats",
        ])

        assert result.returncode == 0
        assert "Total Cases: 0" in result.stdout

    def test_cli_clean_by_severity(self, benchmark_json, tmp_path):
        """重要度でクリーン"""
        storage_dir = tmp_path / "failures"

        # 先に収集
        run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])

        # 重要度でクリーン
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "clean",
            "--low-severity",
            "0.8",
        ])

        assert result.returncode == 0
        assert "Cleaned" in result.stdout or "Remaining" in result.stdout


class TestCLIIntegration:
    """CLI の統合テスト"""

    def test_full_workflow(self, benchmark_json, tmp_path):
        """フルワークフロー: 収集 → 統計 → 一覧 → エクスポート"""
        storage_dir = tmp_path / "failures"
        output_csv = tmp_path / "report.csv"

        # 1. 収集
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "collect-from-benchmark",
            benchmark_json,
        ])
        assert result.returncode == 0

        # 2. 統計
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "stats",
        ])
        assert result.returncode == 0

        # 3. 一覧
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "list",
            "--top",
            "5",
        ])
        assert result.returncode == 0

        # 4. エクスポート
        result = run_cli_command([
            "--storage-dir",
            str(storage_dir),
            "export",
            str(output_csv),
        ])
        assert result.returncode == 0
        assert output_csv.exists()
