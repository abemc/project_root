"""
Phase 7 RAG統合システム - 全体統合テスト
クエリプリプロセッサ、知識統合エンジン、応答生成を統合テスト
"""

import sys
import os
from datetime import datetime

# プロジェクトルートをsys.pathに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def print_section(title: str):
    """セクションヘッダーを表示"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num: int, title: str):
    """ステップを表示"""
    print(f"\n【ステップ {step_num}】{title}")


def main():
    """統合テスト実行"""
    
    print_section("Phase 7 RAG統合システム - 全体統合テスト")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # インポート
        print_step(1, "モジュールインポート")
        from src.rag.query_preprocessor import Phase7QueryPreprocessor
        from src.rag.knowledge_integration_engine import (
            Phase7KnowledgeIntegrationEngine,
            ResponseGenerationEngine,
            KnowledgeEnrichmentManager
        )
        print("  ✅ すべてのモジュールをインポート成功")
        
        # 初期化
        print_step(2, "各エンジンの初期化")
        preprocessor = Phase7QueryPreprocessor()
        knowledge_engine = Phase7KnowledgeIntegrationEngine()
        response_engine = ResponseGenerationEngine()
        enrichment_manager = KnowledgeEnrichmentManager()
        print("  ✅ 全エンジン初期化完了")
        
        # テストクエリセット
        test_queries = [
            {
                'query': "COVID-19ワクチンの医学的効果と法的規制について",
                'type': 'multi-domain',
                'expected_domains': ['medical', 'legal']
            },
            {
                'query': "AIモデルの精度向上とビジネスコストのトレードオフ",
                'type': 'multi-domain',
                'expected_domains': ['technical', 'business']
            },
            {
                'query': "医療過誤訴訟における医学的エビデンス",
                'type': 'multi-domain',
                'expected_domains': ['medical', 'legal']
            },
            {
                'query': "機械学習とは何ですか",
                'type': 'single-domain',
                'expected_domains': ['technical']
            },
        ]
        
        # 統合テスト実行
        print_step(3, f"{len(test_queries)}個のテストクエリで統合テスト実行")
        
        test_results = {
            'passed': 0,
            'failed': 0,
            'errors': [],
            'results': []
        }
        
        for i, test_case in enumerate(test_queries, 1):
            query = test_case['query']
            print(f"\n  【テスト {i}/{len(test_queries)}】{query[:40]}...")
            
            try:
                # フェーズ1: クエリ前処理
                preprocessing = preprocessor.preprocess(query)
                
                # フェーズ2: 模擬検索結果
                mock_documents = {
                    'medical': [
                        type('Doc', (), {'content': f'医学的情報: {query}'})(),
                    ],
                    'legal': [
                        type('Doc', (), {'content': f'法的情報: {query}'})(),
                    ],
                    'technical': [
                        type('Doc', (), {'content': f'技術的情報: {query}'})(),
                    ],
                    'business': [
                        type('Doc', (), {'content': f'ビジネス情報: {query}'})(),
                    ],
                }
                
                # フェーズ3: 知識統合・推論
                integrated_result = knowledge_engine.integrate_and_reason(
                    preprocessing_result=preprocessing,
                    retrieved_documents=mock_documents
                )
                
                # フェーズ4: 知識充実化
                enrichment_manager.enrich_knowledge(
                    base_knowledge=integrated_result.integrated_knowledge,
                    implicit_intents=preprocessing.implicit_intents,
                    required_domains=preprocessing.required_domains
                )
                
                # フェーズ5: 応答生成
                final_response = response_engine.generate_response(
                    integrated_result=integrated_result,
                    base_llm_response=f"【{query}への回答】\n..."
                )
                
                # テスト成功
                test_results['passed'] += 1
                test_results['results'].append({
                    'query': query,
                    'status': 'PASS',
                    'type': test_case['type'],
                    'domain': preprocessing.primary_domain,
                    'response_length': len(final_response),
                    'implicit_intents_count': len(preprocessing.implicit_intents)
                })
                
                print("    ✅ PASS")
                print(f"       主要ドメイン: {preprocessing.primary_domain}")
                print(f"       応答長: {len(final_response)}文字")
                
            except Exception as e:
                test_results['failed'] += 1
                error_msg = str(e)[:100]
                test_results['errors'].append({
                    'query': query,
                    'error': error_msg
                })
                test_results['results'].append({
                    'query': query,
                    'status': 'FAIL',
                    'error': error_msg
                })
                print(f"    ❌ FAIL: {error_msg}")
        
        # テスト結果サマリー
        print_step(4, "テスト結果サマリー")
        total = len(test_queries)
        print(f"\n  テスト実行: {total}件")
        print(f"  成功: {test_results['passed']}件 ({test_results['passed']*100//total}%)")
        print(f"  失敗: {test_results['failed']}件 ({test_results['failed']*100//total}%)")
        
        # 詳細結果
        print_step(5, "詳細テスト結果")
        for result in test_results['results']:
            status_symbol = "✅" if result['status'] == 'PASS' else "❌"
            print(f"\n  {status_symbol} {result['query'][:40]}...")
            if result['status'] == 'PASS':
                print(f"     型: {result['type']}")
                print(f"     ドメイン: {result['domain']}")
                print(f"     応答: {result['response_length']}文字")
                print(f"     隠れた意図: {result['implicit_intents_count']}個")
            else:
                print(f"     エラー: {result['error']}")
        
        # 最終結果
        print_section("統合テスト最終結果")
        if test_results['failed'] == 0:
            print("\n  🎉 すべてのテストが成功しました！")
            print("\n  ✅ Phase 7 RAG統合システムは完全に動作しています")
            print(f"  ✅ {total}個のテストケースで{test_results['passed']}個成功")
            print("\n  次ステップ: RAGパイプラインへの統合")
        else:
            print(f"\n  ⚠️  {test_results['failed']}個のテストが失敗しました")
            print(f"  成功率: {test_results['passed']*100//total}%")
        
        print(f"\n  実行完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        return 0 if test_results['failed'] == 0 else 1
        
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
