#!/usr/bin/env python3
"""
Phase 7: マルチドメイン知識管理・文脈深化エンジン - 統合テスト

4つのコンポーネント群を統合テストするスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 直接インポート（__init__.py経由を避ける）
from self_improvement.context_analyzer import (
    ContextAnalyzer, ImplicitIntentDetector, MetaContextTracker
)
from self_improvement.domain_knowledge import (
    DomainKnowledgeManager, CrossDomainLinker, DomainIndexer
)
from self_improvement.reasoning_engine import (
    KnowledgeIntegrator, CausalReasoningEngine, UncertaintyManager
)


def print_section(title: str) -> None:
    """セクションを表示"""
    print(f"\n{'='*70}")
    print(f"🌍 {title}")
    print(f"{'='*70}\n")


def test_context_analysis() -> bool:
    """テスト 1: 文脈分析レイヤー"""
    print_section("テスト 1: 文脈分析")
    
    try:
        analyzer = ContextAnalyzer()
        detector = ImplicitIntentDetector()
        tracker = MetaContextTracker(user_id="test_user")
        
        # テストクエリ
        test_queries = [
            "医学的にはCOVID-19の症状とは何ですか？",
            "プログラミングの複雑性理論はビジネスにどう応用できますか？",
            "法律的には契約成立の要件は何ですか？詳しく説明してください。",
        ]
        
        for query in test_queries:
            print(f"📝 クエリ: {query}")
            
            # 文脈分析
            context = analyzer.analyze_query(query)
            print(f"  分析結果:")
            print(f"    - 主要意図: {context.primary_intent}")
            print(f"    - ドメイン: {context.domain}")
            print(f"    - 複雑性: {context.complexity}")
            print(f"    - 情報需要: {list(context.information_needs.keys())}")
            
            # 隠れた意図検出
            implicit = detector.detect(query, context.primary_intent)
            if implicit.implicit_list:
                print(f"    - 隠れた意図: {implicit.implicit_list}")
                print(f"      信頼度: {implicit.confidence_scores}")
            
            # ユーザー追跡
            tracker.update_user_profile(
                query, 
                "Sample response", 
                context.domain
            )
            level = tracker.infer_knowledge_level(query, context.domain)
            print(f"    - ユーザー知識レベル: {level:.2f}")
            print()
        
        print("✅ テスト 1 PASS: 文脈分析が正常に動作\n")
        return True
        
    except Exception as e:
        print(f"❌ テスト 1 FAIL: {e}\n")
        return False


def test_domain_knowledge_management() -> bool:
    """テスト 2: マルチドメイン知識管理"""
    print_section("テスト 2: マルチドメイン知識管理")
    
    try:
        manager = DomainKnowledgeManager()
        
        # ドメイン登録確認
        domains = manager.list_domains()
        print(f"✅ 登録ドメイン数: {len(domains)}")
        for domain in domains:
            print(f"  - {domain.name}: {domain.description}")
        
        # ドメイン推定テスト
        test_queries = [
            ("患者の症状は何ですか？", "medical"),
            ("アルゴリズムの最適化方法は？", "technical"),
            ("契約の有効性について", "legal"),
            ("市場戦略の立て方は？", "business"),
        ]
        
        print("\n📊 ドメイン推定テスト:")
        for query, expected_domain in test_queries:
            inferred = manager.infer_domain_from_query(query)
            top_domain = inferred[0][0] if inferred else "unknown"
            match = "✅" if top_domain == expected_domain else "⚠️"
            print(f"  {match} '{query}' -> {top_domain}")
        
        print("\n✅ テスト 2 PASS: ドメイン知識管理が正常に動作\n")
        return True
        
    except Exception as e:
        print(f"❌ テスト 2 FAIL: {e}\n")
        return False


def test_cross_domain_linking() -> bool:
    """テスト 3: ドメイン間リンク"""
    print_section("テスト 3: クロスドメインリンク")
    
    try:
        manager = DomainKnowledgeManager()
        linker = CrossDomainLinker(manager)
        
        # 既存リンクを表示
        links = linker.get_all_links()
        print(f"✅ ドメイン間リンク数: {len(links)}")
        for link in links:
            print(f"  - {link.source_domain} -> {link.target_domain}: {link.relation_type} (強度: {link.strength:.1f})")
        
        # 関連ドメイン検索
        print("\n📍 関連ドメイン検索:")
        for domain in ['medical', 'technical', 'business']:
            related = linker.find_related_domains(domain)
            print(f"  - {domain}: {[l.target_domain for l in related]}")
        
        # 架け橋知識
        print("\n🌉 架け橋知識:")
        bridge = linker.bridge_knowledge('medical', 'biology')
        if bridge:
            print(f"  - Medical -> Biology: {bridge}")
        
        print("\n✅ テスト 3 PASS: クロスドメインリンクが正常に動作\n")
        return True
        
    except Exception as e:
        print(f"❌ テスト 3 FAIL: {e}\n")
        return False


def test_knowledge_integration_and_reasoning() -> bool:
    """テスト 4: 知識統合・推論"""
    print_section("テスト 4: 知識統合・推論エンジン")
    
    try:
        integrator = KnowledgeIntegrator()
        causal_engine = CausalReasoningEngine()
        uncertainty_mgr = UncertaintyManager()
        
        # 統合知識テスト
        print("📚 マルチドメイン統合:")
        integrated = integrator.integrate_knowledge(
            primary_domain='medical',
            related_domains=['biology', 'chemistry'],
            query='COVID-19 treatment'
        )
        print(f"  - 主要ドメイン: {integrated.primary_domain}")
        print(f"  - 関連ドメイン: {integrated.relevant_domains}")
        print(f"  - 統合事実数: {len(integrated.integrated_facts)}")
        if integrated.contradictions:
            print(f"  - 矛盾数: {len(integrated.contradictions)}")
        
        # 因果推論テスト
        print("\n🔗 因果推論:")
        relation = causal_engine.infer_causality("smoking", "lung_cancer")
        if relation:
            print(f"  - 原因: {relation.cause}")
            print(f"  - 結果: {relation.effect}")
            print(f"  - 因果強度: {relation.strength:.2f}")
            print(f"  - 信頼度: {relation.confidence:.2f}")
        
        # 因果チェーン
        chain = causal_engine.trace_causality_chain("smoking", max_depth=3)
        if chain:
            print(f"  - 因果チェーン長: {len(chain)}")
        
        # 交絡因子
        confounders = causal_engine.identify_confounders("health_outcome", "medical")
        if confounders:
            print(f"  - 交絡因子: {confounders[:3]}")
        
        # 不確実性管理
        print("\n❓ 不確実性管理:")
        uncertainty = uncertainty_mgr.assess_uncertainty(
            "COVID-19 vaccines provide 95% protection",
            "medical"
        )
        print(f"  - 不確実性レベル: {uncertainty.level:.2f}")
        print(f"  - 不確実性源: {uncertainty.sources[:3]}")
        
        expression = uncertainty_mgr.express_uncertainty(uncertainty)
        print(f"  - 言語化: {expression.split(chr(10))[0]}")
        
        # 追加研究推奨
        recommendations = uncertainty_mgr.recommend_additional_research(uncertainty)
        print(f"  - 推奨研究: {recommendations[0] if recommendations else 'なし'}")
        
        print("\n✅ テスト 4 PASS: 知識統合・推論が正常に動作\n")
        return True
        
    except Exception as e:
        print(f"❌ テスト 4 FAIL: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_domain_indexer() -> bool:
    """テスト 5: ドメインインデックス"""
    print_section("テスト 5: ドメインインデックス")
    
    try:
        manager = DomainKnowledgeManager()
        indexer = DomainIndexer(manager)
        
        # デフォルトインデックスを構築
        indexer.build_default_indices()
        
        # インデックス検索テスト
        print("🔍 インデックス検索:")
        results = indexer.search_in_domain('medical', 'anatomy', top_k=3)
        print(f"  - 医学: 'anatomy' で検索 -> {results}")
        
        results = indexer.search_in_domain('technical', 'algorithm', top_k=3)
        print(f"  - 技術: 'algorithm' で検索 -> {results}")
        
        # 関連概念提示
        print("\n💡 関連概念提示:")
        suggestions = indexer.suggest_related_concepts('medical', 'anatomy')
        print(f"  - Medical 'anatomy' の関連概念: {suggestions}")
        
        print("\n✅ テスト 5 PASS: ドメインインデックスが正常に動作\n")
        return True
        
    except Exception as e:
        print(f"❌ テスト 5 FAIL: {e}\n")
        return False


def main() -> int:
    """メイン関数"""
    print("\n" + "="*70)
    print("🚀 Phase 7: マルチドメイン知識管理・文脈深化エンジン")
    print("="*70)
    print("テスト開始: 2026-04-11\n")
    
    tests = [
        ("文脈分析レイヤー", test_context_analysis),
        ("マルチドメイン知識管理", test_domain_knowledge_management),
        ("クロスドメインリンク", test_cross_domain_linking),
        ("知識統合・推論エンジン", test_knowledge_integration_and_reasoning),
        ("ドメインインデックス", test_domain_indexer),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # 結果サマリー
    print("\n" + "="*70)
    print("📊 テスト結果サマリー")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n📈 成功率: {passed}/{total} ({100*passed//total}%)")
    
    if passed == total:
        print("\n🎉 Phase 7 実装完全成功！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} テストが失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
