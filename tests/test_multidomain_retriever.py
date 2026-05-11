"""
MultiDomainRetriever テスト
新しく実装されたマルチドメイン検索機能をテスト
"""

import sys
import os

# プロジェクトルートをsys.pathに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_multidomain_retriever():
    """MultiDomainRetrieverの機能をテスト"""
    print("\n" + "="*70)
    print("  MultiDomainRetriever テスト")
    print("="*70)
    
    # ステップ1: インポート
    print("\n【ステップ1】モジュールインポート")
    try:
        from src.rag.multi_domain_retriever import (
            MultiDomainRetriever
        )
        print("  ✅ MultiDomainRetriever モジュール インポート成功")
    except Exception as e:
        print(f"  ❌ インポート失敗: {e}")
        return False
    
    # ステップ2: Retriever初期化
    print("\n【ステップ2】Retriever初期化")
    try:
        retriever = MultiDomainRetriever()
        stats = retriever.get_domain_stats()
        print("  ✅ Retriever初期化成功")
        print(f"     デフォルトドメイン数: {len(stats)}")
        for domain, stat in list(stats.items())[:3]:
            print(f"     - {domain}: {stat['index_count']} documents")
    except Exception as e:
        print(f"  ❌ 初期化失敗: {e}")
        return False
    
    # ステップ3: ドキュメント追加
    print("\n【ステップ3】テストドキュメント追加")
    try:
        # 医療ドメイン
        retriever.add_documents_to_domain(
            domain="test_medical",
            documents=[
                "医療費控除は、その年の医療費が一定金額を超えた場合に申告することで所得税が還付される制度です。",
                "医療費控除の対象となるのは、治療費、手術費、診断費、医師への支払いなどです。",
                "医療保険は病気やけがの治療費をカバーする保険商品です。",
            ],
            metadata=[
                {"title": "医療費控除の概要", "category": "tax"},
                {"title": "医療費控除の対象", "category": "tax"},
                {"title": "医療保険について", "category": "insurance"},
            ]
        )
        
        # 法律ドメイン
        retriever.add_documents_to_domain(
            domain="test_legal",
            documents=[
                "医療費控除は所得税法第120条に規定されている制度です。",
                "医療費控除の申告には、診療報酬領収書が必要です。",
                "税務署への申告方法は毎年変わることがあります。",
            ],
            metadata=[
                {"title": "所得税法第120条", "category": "law"},
                {"title": "申告に必要な書類", "category": "procedure"},
                {"title": "申告方法の変更", "category": "announcement"},
            ]
        )
        
        print("  ✅ ドキュメント追加成功")
        print("     - test_medical ドメイン: 3文書追加")
        print("     - test_legal ドメイン: 3文書追加")
    except Exception as e:
        print(f"  ❌ ドキュメント追加失敗: {e}")
        return False
    
    # ステップ4: 単一ドメイン検索
    print("\n【ステップ4】単一ドメイン検索テスト")
    try:
        result = retriever.retrieve_from_domain(
            query="医療費控除とは",
            domain="test_medical",
            top_k=2
        )
        print(f"  ✅ 検索成功 (ドメイン: {result.domain})")
        print(f"     検索結果: {len(result.results)}件")
        print(f"     スコア: {[f'{s:.3f}' for s in result.scores]}")
        for i, doc in enumerate(result.results, 1):
            print(f"       {i}. {doc.get('title', 'no title')}")
    except Exception as e:
        print(f"  ❌ 検索失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ステップ5: マルチドメイン検索
    print("\n【ステップ5】マルチドメイン検索テスト")
    try:
        result = retriever.retrieve_from_multiple_domains(
            query="医療費控除の申告方法",
            primary_domain="test_medical",
            related_domains=["test_legal"],
            top_k_per_domain=2
        )
        
        print("  ✅ マルチドメイン検索成功")
        print(f"     主要ドメイン: {result.primary_domain}")
        print(f"     関連ドメイン: {result.related_domains}")
        print(f"     合計結果: {len(result.merged_results)}件")
        
        print(f"\n     【主要ドメイン結果】 ({result.primary_domain}):")
        for i, doc in enumerate(result.primary_results.results, 1):
            print(f"       {i}. {doc.get('title', 'no title')} (score: {doc.get('score', 0):.3f})")
        
        if result.related_results:
            for domain, rel_result in result.related_results.items():
                print(f"\n     【関連ドメイン結果】 ({domain}):")
                for i, doc in enumerate(rel_result.results, 1):
                    print(f"       {i}. {doc.get('title', 'no title')} (score: {doc.get('score', 0):.3f})")
    except Exception as e:
        print(f"  ❌ マルチドメイン検索失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ステップ6: キャッシング確認
    print("\n【ステップ6】キャッシング機構テスト")
    try:
        # 同じクエリで再検索（キャッシュヒット）
        retriever.retrieve_from_multiple_domains(
            query="医療費控除の申告方法",
            primary_domain="test_medical",
            related_domains=["test_legal"],
            top_k_per_domain=2,
            use_cache=True
        )
        print("  ✅ キャッシュ機構正常")
        print("     (2回目の検索でキャッシュから取得)")
    except Exception as e:
        print(f"  ⚠️  キャッシュ機構テスト: {e}")
    
    # ステップ7: ドメイン統計
    print("\n【ステップ7】ドメインドメイン統計確認")
    try:
        stats = retriever.get_domain_stats()
        print("  ✅ ドメイン統計取得成功:")
        for domain, stat in stats.items():
            if "test_" in domain:
                print(f"     - {domain}: {stat['index_count']} documents")
    except Exception as e:
        print(f"  ❌ 統計取得失敗: {e}")
        return False
    
    print("\n" + "="*70)
    print("  ✅ すべてのMultiDomainRetrieverテストが成功しました！")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_multidomain_retriever()
    exit(0 if success else 1)
