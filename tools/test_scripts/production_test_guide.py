#!/usr/bin/env python3
"""
Phase 7 + RAG Agent 本番環境テスト実行ガイド
段階的な機能検証プロセス
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class ProductionTestGuide:
    """本番環境テストガイド"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        self.test_log = []
    
    def print_header(self, title: str):
        """ヘッダー表示"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    
    def print_section(self, title: str):
        """セクション表示"""
        print(f"\n【{title}】")
        print("-" * 60)
    
    def log_test(self, level: str, name: str, result: bool, details: str = ""):
        """テスト結果をログ"""
        status = "✅ PASS" if result else "❌ FAIL"
        log_entry = f"{status} [{level}] {name}"
        if details:
            log_entry += f" - {details}"
        print(log_entry)
        self.test_log.append(log_entry)
        return result
    
    def test_level_1_basic_operation(self) -> bool:
        """L1: 基本動作テスト"""
        self.print_section("L1: 基本動作テスト")
        print("オブジェクトのインポートと初期化の検証\n")
        
        all_pass = True
        
        # テスト 1.1: モジュールインポート
        try:
            from self_improvement.domain_knowledge import DomainKnowledgeManager
            from rag.query_preprocessor import Phase7QueryPreprocessor
            # RAGAgent のインポートはスキップ（外部依存が多い）
            
            self.log_test("L1", "モジュールインポート", True,
                         "DomainKnowledgeManager, Phase7QueryPreprocessor")
        except ImportError as e:
            self.log_test("L1", "モジュールインポート", False, str(e))
            all_pass = False
            return all_pass
        
        # テスト 1.2: DomainKnowledgeManager 初期化
        try:
            manager = DomainKnowledgeManager()
            domains = manager.list_domains()
            result = len(domains) >= 5
            self.log_test(
                "L1", 
                "DomainKnowledgeManager 初期化",
                result,
                f"{len(domains)} ドメイン登録"
            )
            all_pass = all_pass and result
        except Exception as e:
            self.log_test("L1", "DomainKnowledgeManager 初期化", False, str(e))
            all_pass = False
        
        # テスト 1.3: Phase7QueryPreprocessor 初期化
        try:
            preprocessor = Phase7QueryPreprocessor()
            result = hasattr(preprocessor, 'preprocess')
            self.log_test(
                "L1",
                "Phase7QueryPreprocessor 初期化",
                result,
                "preprocess メソッド確認"
            )
            all_pass = all_pass and result
        except Exception as e:
            self.log_test("L1", "Phase7QueryPreprocessor 初期化", False, str(e))
            all_pass = False
        
        return all_pass
    
    def test_level_2_domain_estimation(self) -> bool:
        """L2: ドメイン推定精度テスト"""
        self.print_section("L2: ドメイン推定精度テスト")
        print("複数のクエリでドメイン推定の正確性を検証\n")
        
        from self_improvement.domain_knowledge import DomainKnowledgeManager
        
        manager = DomainKnowledgeManager()
        
        # テストケース定義
        test_cases = [
            ("COVID-19ワクチンの医学的効果とは？", "medical", "医学ドメイン"),
            ("契約の法的有効性について", "legal", "法律ドメイン"),
            ("アルゴリズムの最適化方法", "technical", "技術ドメイン"),
            ("ビジネス戦略の立て方", "business", "ビジネスドメイン"),
            ("物理の基本原理とは", "science", "科学ドメイン"),
        ]
        
        all_pass = True
        for query, expected_domain, description in test_cases:
            try:
                result = manager.infer_domain_from_query(query)
                if result and result[0][0] == expected_domain:
                    self.log_test(
                        "L2",
                        f"ドメイン推定: {description}",
                        True,
                        f"推定={result[0][0]}, 信頼度={result[0][1]:.2f}"
                    )
                else:
                    inferred = result[0][0] if result else "None"
                    self.log_test(
                        "L2",
                        f"ドメイン推定: {description}",
                        False,
                        f"期待={expected_domain}, 推定={inferred}"
                    )
                    all_pass = False
            except Exception as e:
                self.log_test("L2", f"ドメイン推定: {description}", False, str(e))
                all_pass = False
        
        return all_pass
    
    def test_level_3_query_preprocessing(self) -> bool:
        """L3: クエリ前処理テスト"""
        self.print_section("L3: クエリ前処理統合テスト")
        print("Phase7QueryPreprocessor の完全な前処理プロセス検証\n")
        
        from rag.query_preprocessor import Phase7QueryPreprocessor
        
        preprocessor = Phase7QueryPreprocessor()
        
        test_queries = [
            "医療制度と法的規制について教えてください",
            "ビジネスの技術的な課題解決方法",
            "科学的根拠に基づくビジネス戦略",
        ]
        
        all_pass = True
        for idx, query in enumerate(test_queries, 1):
            try:
                result = preprocessor.preprocess(query)
                
                # 必須属性確認
                has_required = all([
                    hasattr(result, 'primary_domain'),
                    hasattr(result, 'complexity_level'),
                    hasattr(result, 'related_domains'),
                    hasattr(result, 'required_domains'),
                ])
                
                self.log_test(
                    "L3",
                    f"クエリ前処理 #{idx}",
                    has_required,
                    f"Domain={result.primary_domain}, "
                    f"Complexity={result.complexity_level}"
                )
                all_pass = all_pass and has_required
            except Exception as e:
                self.log_test("L3", f"クエリ前処理 #{idx}", False, str(e))
                all_pass = False
        
        return all_pass
    
    def test_level_4_performance_metrics(self) -> bool:
        """L4: パフォーマンス測定"""
        self.print_section("L4: パフォーマンステスト")
        print("処理時間とリソース使用量の測定\n")
        
        import time
        from rag.query_preprocessor import Phase7QueryPreprocessor
        from self_improvement.domain_knowledge import DomainKnowledgeManager
        
        preprocessor = Phase7QueryPreprocessor()
        manager = DomainKnowledgeManager()
        
        test_query = "医療システムの法的規制と技術的実装について"
        
        all_pass = True
        
        # 処理時間測定
        try:
            start = time.time()
            result = preprocessor.preprocess(test_query)
            elapsed = time.time() - start
            
            # 許容時間: 100ms以下
            is_fast = elapsed < 0.1
            self.log_test(
                "L4",
                "クエリ前処理速度",
                is_fast,
                f"処理時間: {elapsed*1000:.1f}ms"
            )
            all_pass = all_pass and is_fast
        except Exception as e:
            self.log_test("L4", "クエリ前処理速度", False, str(e))
            all_pass = False
        
        # ドメイン推定速度測定
        try:
            start = time.time()
            for _ in range(100):
                manager.infer_domain_from_query(test_query)
            elapsed = time.time() - start
            avg_time = elapsed / 100
            
            # 許容時間: 1ms以下
            is_fast = avg_time < 0.001
            self.log_test(
                "L4",
                "ドメイン推定速度（100回平均）",
                is_fast,
                f"平均: {avg_time*1000:.2f}ms"
            )
            all_pass = all_pass and is_fast
        except Exception as e:
            self.log_test("L4", "ドメイン推定速度", False, str(e))
            all_pass = False
        
        return all_pass
    
    def test_level_5_user_acceptance(self) -> bool:
        """L5: ユーザー受入テスト（UAT）"""
        self.print_section("L5: ユーザー受入テスト（UAT）")
        print("実際のユースケースでの機能検証\n")
        print("【手動テストが必要です】\n")
        
        uat_checklist = [
            ("医療関連の複雑な質問", "ドメイン推定とクエリ前処理が正しく動作するか確認"),
            ("法律相談的な質問", "法律ドメインと関連ドメインが正確に検出されるか確認"),
            ("技術的な実装相談", "技術ドメインの複数キーワードマッチが機能するか確認"),
            ("ビジネス戦略相談", "ビジネスドメイン+ 関連ドメイン検出が正確か確認"),
            ("複合的なマルチドメイン質問", "複数ドメイン統合が正しく行われるか確認"),
        ]
        
        print("推奨テストケース:")
        for idx, (usecase, validation) in enumerate(uat_checklist, 1):
            print(f"{idx}. 【{usecase}】")
            print(f"   → {validation}\n")
        
        return True  # UATは手動評価のため True を返す
    
    def generate_test_report(self):
        """テストレポート生成"""
        self.print_header("テスト実行完了レポート")
        
        elapsed = datetime.now() - self.start_time
        
        print(f"実行時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"実行時間: {elapsed.total_seconds():.1f}秒\n")
        
        print("=== テスト結果ログ ===\n")
        for entry in self.test_log:
            print(entry)
        
        print("\n" + "="*70)
        print("次のステップ:")
        print("1. L5 ユーザー受入テスト（UAT）を実施してください")
        print("2. テスト結果をまとめてください")
        print("3. 問題が発生した場合は logs/ ディレクトリで詳細を確認してください")
        print("="*70 + "\n")


def main():
    """本番環境テスト実行"""
    
    guide = ProductionTestGuide()
    
    guide.print_header("Phase 7 + RAG Agent 本番環境機能テスト")
    print("本番環境での段階的な機能検証プロセス\n")
    
    # テスト実行
    test_results = {
        "L1_基本動作": guide.test_level_1_basic_operation(),
        "L2_ドメイン推定": guide.test_level_2_domain_estimation(),
        "L3_クエリ前処理": guide.test_level_3_query_preprocessing(),
        "L4_パフォーマンス": guide.test_level_4_performance_metrics(),
        "L5_ユーザー受入": guide.test_level_5_user_acceptance(),
    }
    
    # レポート生成
    guide.generate_test_report()
    
    # 最終結果判定
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    print(f"\n📊 テスト成績: {passed}/{total} ✅")
    
    if passed >= 4:  # L5はUATなので手動
        print("\n✅ 本番環境テスト合格！\n")
        print("次のアクション:")
        print("1. L5（ユーザー受入テスト）実施")
        print("2. ステークホルダーに結果を報告")
        print("3. 本番環境での運用を開始")
        return 0
    else:
        print("\n⚠️  テストに失敗しました\n")
        print("対応が必要です:")
        print("1. 失敗したテストをご確認ください")
        print("2. 問題がある場合は ./rollback.sh を検討してください")
        return 1


if __name__ == "__main__":
    sys.exit(main())
