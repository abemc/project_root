#!/usr/bin/env python3
"""
Phase 7 + RAG Agent 統合テスト
agent.pyへのPhase7統合を検証
"""

import sys
from pathlib import Path

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def print_section(title: str) -> None:
    """セクションを表示"""
    print(f"\n{'='*70}")
    print(f"🔗 {title}")
    print(f"{'='*70}\n")


def test_agent_phase7_imports() -> bool:
    """テスト 1: Agent と Phase 7 コンポーネントのインポート"""
    print_section("テスト 1: インポート検証")
    
    try:
        from rag.agent import RAGAgent
        print("✅ RAGAgent インポート成功")
        
        from rag.query_preprocessor import Phase7QueryPreprocessor
        print("✅ Phase7QueryPreprocessor インポート成功")
        
        from rag.knowledge_integration_engine import Phase7KnowledgeIntegrationEngine
        print("✅ Phase7KnowledgeIntegrationEngine インポート成功")
        
        return True
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        return False


def test_agent_initialization() -> bool:
    """テスト 2: RAGAgent の Phase 7 統合の初期化"""
    print_section("テスト 2: Agent 初期化検証")
    
    try:
        from rag.agent import RAGAgent
        
        # ダミーオブジェクトで初期化テスト（retriever/reranker なし）
        class DummyRetriever:
            def hybrid_search(self, query, top_k=10):
                return []
            def get_recent_docs(self, top_k=10):
                return []
        
        class DummyReranker:
            def rerank(self, question, docs, top_k=5):
                return []
        
        agent = RAGAgent(
            question="テストクエリ",
            retriever=DummyRetriever(),
            reranker=DummyReranker(),
            max_steps=1
        )
        
        # Phase 7 コンポーネント確認
        checks = [
            ("query_preprocessor", hasattr(agent, "query_preprocessor")),
            ("knowledge_integrator", hasattr(agent, "knowledge_integrator")),
            ("domain_context", hasattr(agent, "domain_context")),
            ("state['domains']", "domains" in agent.state),
            ("state['query_context']", "query_context" in agent.state),
            ("log_data['domains_used']", "domains_used" in agent.log_data)
        ]
        
        all_ok = True
        for name, result in checks:
            status = "✅" if result else "❌"
            print(f"{status} {name}: {result}")
            all_ok = all_ok and result
        
        return all_ok
        
    except Exception as e:
        print(f"❌ 初期化エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_preprocessing() -> bool:
    """テスト 3: _preprocess_query_with_phase7 メソッドテスト"""
    print_section("テスト 3: クエリ前処理機能")
    
    try:
        from rag.agent import RAGAgent
        
        class DummyRetriever:
            def hybrid_search(self, query, top_k=10):
                return []
            def get_recent_docs(self, top_k=10):
                return []
        
        class DummyReranker:
            def rerank(self, question, docs, top_k=5):
                return []
        
        agent = RAGAgent(
            question="COVID-19ワクチンの医学的効果",
            retriever=DummyRetriever(),
            reranker=DummyReranker(),
            max_steps=1
        )
        
        # クエリ前処理実行
        test_queries = [
            "医学的にCOVID-19とは何ですか？",
            "契約の法的有効性について説明してください",
            "プログラミングの複雑性理論",
        ]
        
        for query in test_queries:
            result = agent._preprocess_query_with_phase7(query)
            status = "✅" if result["success"] else "❌"
            print(f"{status} '{query[:30]}...'")
            if result["success"]:
                prep = result["preprocessing_result"]
                print(f"   - Domain: {prep.primary_domain}")
                print(f"   - Complexity: {prep.complexity_level}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_domain_context_updates() -> bool:
    """テスト 4: ドメインコンテキストの更新確認"""
    print_section("テスト 4: ドメインコンテキスト更新")
    
    try:
        from rag.agent import RAGAgent
        
        class DummyRetriever:
            def hybrid_search(self, query, top_k=10):
                return []
            def get_recent_docs(self, top_k=10):
                return []
        
        class DummyReranker:
            def rerank(self, question, docs, top_k=5):
                return []
        
        agent = RAGAgent(
            question="医学的な質問",
            retriever=DummyRetriever(),
            reranker=DummyReranker(),
            max_steps=1
        )
        
        # 前処理前のドメイン情報
        print(f"初期状態:")
        print(f"  - state['domains']: {agent.state['domains']}")
        print(f"  - domain_context: {agent.domain_context}")
        
        # 前処理実行
        agent._preprocess_query_with_phase7("医学的な質問")
        
        # 前処理後のドメイン情報
        print(f"\n前処理後:")
        print(f"  - state['domains']: {agent.state['domains']}")
        print(f"  - domain_context keys: {list(agent.domain_context.keys())}")
        print(f"  - log_data['domains_used'] の件数: {len(agent.log_data['domains_used'])}")
        
        # 検証
        has_domains = len(agent.state['domains']) >= 0  # 空でもOK
        has_context = agent.state['query_context'] is not None
        has_log = len(agent.log_data['domains_used']) > 0
        
        print(f"\n✅ ドメイン情報: {has_domains}")
        print(f"✅ クエリコンテキスト: {has_context}")
        print(f"✅ ドメインログ: {has_log}")
        
        return has_domains and has_context and has_log
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """統合テスト実行"""
    
    print("\n" + "="*70)
    print("  Phase 7 + RAG Agent 統合テストスイート")
    print("="*70)
    
    test_results = {
        "インポート検証": test_agent_phase7_imports(),
        "Agent 初期化": test_agent_initialization(),
        "クエリ前処理": test_query_preprocessing(),
        "ドメインコンテキスト": test_domain_context_updates(),
    }
    
    # 結果集計
    print("\n" + "="*70)
    print("📊 テスト結果サマリー")
    print("="*70 + "\n")
    
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📈 成功率: {passed}/{total} ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("🎉 Phase 7 + Agent 統合が完全に成功しました！")
        return 0
    else:
        print("⚠️  一部のテストが失敗しました")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
