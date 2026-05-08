#!/usr/bin/env python3
"""
推論エンジンの実践的なデモンストレーション

このスクリプトを実行すると、3つの推論エンジンが
どのように動作するかを実際に体験できます。
"""

import sys
sys.path.insert(0, 'src')

from self_improvement.reasoning_engine import (
    KnowledgeIntegrator,
    CausalReasoningEngine,
    UncertaintyManager,
)

def print_section(title):
    """セクションヘッダーを表示"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def demo_knowledge_integrator():
    """デモ: KnowledgeIntegrator（知識統合エンジン）"""
    print_section("デモ1️⃣: KnowledgeIntegrator（知識統合エンジン）")
    
    print("【説明】")
    print("複数のドメイン知識を統合し、矛盾を検出・解決するエンジンです。\n")
    
    ki = KnowledgeIntegrator()
    
    # テスト1: 医学 + 法律 + 技術
    print("【テストケース1】医療用ロボットの承認取得")
    print("-" * 80)
    
    integrated = ki.integrate_knowledge(
        primary_domain="medical",
        related_domains=["legal", "technical"],
        query="medical robot approval process"
    )
    
    print(f"✓ 主要ドメイン: {integrated.primary_domain.upper()}")
    print(f"✓ 関連ドメイン: {', '.join([d.upper() for d in integrated.relevant_domains])}")
    
    print(f"\n【統合事実】")
    for i, fact in enumerate(integrated.integrated_facts, 1):
        print(f"  {i}. {fact['domain'].upper()}: {fact['fact']}")
        print(f"     関連度: {fact['relevance']:.1%}\n")
    
    print(f"【検出された矛盾】")
    if integrated.contradictions:
        for i, cont in enumerate(integrated.contradictions, 1):
            print(f"  {i}. {cont['domain1'].upper()} vs {cont['domain2'].upper()}")
            print(f"     問題: {cont['issue']}")
            print(f"     解決策: {cont['resolution']}\n")
    else:
        print("  矛盾なし\n")
    
    print(f"【統合的説明】")
    print(integrated.synthesis)
    
    # テスト2: 視点の違いを説明
    print("\n" + "-" * 80)
    print("\n【テストケース2】医学と法律の視点の相違")
    print("-" * 80)
    
    perspective = ki.explain_perspective_differences(
        "medical", "legal", "医療機器の承認基準"
    )
    print(perspective)


def demo_causal_reasoning_engine():
    """デモ: CausalReasoningEngine（因果推論エンジン）"""
    print_section("デモ2️⃣: CausalReasoningEngine（因果推論エンジン）")
    
    print("【説明】")
    print("「相関」ではなく「因果関係」を認識し、")
    print("因果チェーンを追跡するエンジンです。\n")
    
    cre = CausalReasoningEngine()
    
    # テスト1: 因果関係の推定
    print("【テストケース1】因果関係の推定")
    print("-" * 80)
    
    test_pairs = [
        ("smoking habits", "lung cancer development"),
        ("customer satisfaction", "customer retention rate"),
        ("algorithm optimization", "system performance"),
    ]
    
    for cause, effect in test_pairs:
        causality = cre.infer_causality(cause, effect)
        
        print(f"\n原因: {cause}")
        print(f"結果: {effect}")
        
        if causality:
            print(f"✓ 因果関係を検出")
            print(f"  因果強度: {causality.strength:.1f}/1.0")
            print(f"  信頼度: {causality.confidence:.1f}/1.0")
        else:
            print(f"✗ 因果関係が十分に明確でない")
    
    # テスト2: 因果チェーンの追跡
    print("\n" + "-" * 80)
    print("\n【テストケース2】因果チェーンの追跡")
    print("-" * 80)
    
    chain = cre.trace_causality_chain("code quality improvement", max_depth=3)
    
    print(f"\nルート原因: \"code quality improvement\"\n")
    print("因果チェーン:")
    
    if chain:
        for i, relation in enumerate(chain, 1):
            print(f"\n  {i}. {relation.cause}")
            print(f"     ↓ (強度: {relation.strength:.1f})")
            print(f"     {relation.effect}")
    else:
        print("  チェーン情報がありません")
    
    # テスト3: 交絡因子の特定
    print("\n" + "-" * 80)
    print("\n【テストケース3】交絡因子の特定")
    print("-" * 80)
    
    # 医学ドメインの交絡因子
    health_confounders = cre.identify_confounders(
        "health outcome", "medical"
    )
    
    print("\n問題: \"健康成果\" に影響する要因は何か？")
    print(f"ドメイン: Medical\n")
    print("検出された交絡因子:")
    for confounder in health_confounders:
        print(f"  • {confounder}")
    
    print("\n【説明】")
    print("これらは直接的な因果関係ではなく、")
    print("「健康成果」に複合的に影響する要因です。")
    
    # テスト4: 反事実分析
    print("\n" + "-" * 80)
    print("\n【テストケース4】反事実分析（Counterfactual Analysis）")
    print("-" * 80)
    
    scenario = "COVID-19 pandemic did not occur"
    analysis = cre.counterfactual_analysis(scenario)
    
    print(f"\n反事実シナリオ: {analysis['scenario']}")
    print(f"定義: {analysis['definition']}")
    
    print(f"\n予測される結果:")
    for outcome in analysis['likely_outcomes']:
        print(f"  ✓ {outcome}")
    
    print(f"\n主な違い:")
    for diff in analysis['key_differences']:
        print(f"  • {diff}")


def demo_uncertainty_manager():
    """デモ: UncertaintyManager（不確実性管理エンジン）"""
    print_section("デモ3️⃣: UncertaintyManager（不確実性管理エンジン）")
    
    print("【説明】")
    print("知識の不確実性レベルを評価し、")
    print("確実な部分と不確実な部分を区別するエンジンです。\n")
    
    um = UncertaintyManager()
    
    # テスト1: 不確実性レベルの評価
    print("【テストケース1】不確実性レベルの評価")
    print("-" * 80)
    
    statements = [
        ("Vaccines provide immunity protection", "medical"),
        ("The climate will change significantly in 2050", "science"),
        ("AI will cause mass unemployment", "business"),
    ]
    
    uncertainty_labels = {
        (0.0, 0.1): "🟢 確実",
        (0.1, 0.3): "🟡 可能性高",
        (0.3, 0.6): "🟠 中程度",
        (0.6, 0.85): "🔴 不確実",
        (0.85, 1.0): "🔴🔴 高度不確実",
    }
    
    for statement, domain in statements:
        uncertainty = um.assess_uncertainty(statement, domain)
        
        print(f"\n【ステートメント】")
        print(f"  {statement}")
        print(f"  ドメイン: {domain.upper()}")
        
        # 不確実性レベルを判定
        level_label = "不明"
        for (low, high), label in uncertainty_labels.items():
            if low <= uncertainty.level < high:
                level_label = label
                break
        
        print(f"\n【評価結果】")
        print(f"  不確実性レベル: {uncertainty.level:.2f} {level_label}")
        print(f"  信頼区間: [{uncertainty.confidence_interval[0]:.2f}, {uncertainty.confidence_interval[1]:.2f}]")
        
        print(f"\n【不確実性の源】")
        for source in uncertainty.sources:
            source_descriptions = {
                'temporal_distance': "将来のことなので予測不確実",
                'measurement_limitation': "測定の限界",
                'conflicting_evidence': "相反する証拠",
                'insufficient_data': "データ不足",
                'general_knowledge_limitation': "一般的な知識の限界",
            }
            desc = source_descriptions.get(source, source)
            print(f"  • {desc}")
        
        print(f"\n【代替解釈】")
        for i, alt in enumerate(uncertainty.alternative_interpretations, 1):
            print(f"  {i}. {alt}")
    
    # テスト2: 不確実性の表現
    print("\n" + "-" * 80)
    print("\n【テストケース2】不確実性の適切な表現")
    print("-" * 80)
    
    print("\n【例】ワクチンの効果について\n")
    
    vaccine_uncertainty = um.assess_uncertainty(
        "Vaccine efficacy is 95 percent with variation by individual",
        "medical"
    )
    
    print("❌ 不適切な表現:")
    print("   \"ワクチンは95%効果があります\"")
    print("   → 誤解を招く、不確実性が表現されていない\n")
    
    print("✅ 適切な表現:")
    print("   \"研究では95%の有効性が示されていますが、")
    print("    個人差があり、時間とともに低下する可能性があります。")
    print("    特に新型変異株に対する効力は更に検討が必要です。\"")
    print("   → 確実性と不確実性が明確")


def interactive_demo():
    """対話的なデモ"""
    print_section("🎮 実験: あなたがクエリを入力してみる")
    
    print("【説明】")
    print("あなたが質問を入力すると、")
    print("推論エンジンがそれを分析します。\n")
    
    ki = KnowledgeIntegrator()
    cre = CausalReasoningEngine()
    um = UncertaintyManager()
    
    # サンプルクエリ
    sample_queries = [
        ("医療用AIシステムの規制承認プロセス", ["medical", "legal", "technical"]),
        ("持続可能な技術投資の効果測定", ["technical", "business", "science"]),
    ]
    
    print("【サンプルクエリ】")
    for i, (query, domains) in enumerate(sample_queries, 1):
        print(f"{i}. {query}")
    
    print("\n【実行例】")
    for query, domains in sample_queries[:1]:  # 最初の1つだけ実行
        print(f"\nクエリ: {query}")
        print(f"推定ドメイン: {', '.join([d.upper() for d in domains])}\n")
        
        # 知識統合
        integrated = ki.integrate_knowledge(
            primary_domain=domains[0],
            related_domains=domains[1:],
            query=query
        )
        
        print("【知識統合結果】")
        print(f"{integrated.synthesis[:200]}...\n")
        
        # 不確実性評価
        uncertainty = um.assess_uncertainty(query, domains[0])
        
        print("【不確実性評価】")
        print(f"不確実性レベル: {uncertainty.level:.2f}")
        print(f"このクエリへの回答信頼度: {(1-uncertainty.level):.1%}")


def main():
    """メイン実行関数"""
    print("\n" + "🤖" * 40)
    print("Phase 7 推論エンジン実践デモンストレーション")
    print("🤖" * 40)
    
    print("""
【このデモが示すもの】

推論エンジンは以下の3つのコンポーネントで構成されています：

1️⃣ KnowledgeIntegrator
   → 複数ドメイン知識を統合し、矛盾を解決
   
2️⃣ CausalReasoningEngine
   → 相関ではなく因果関係を分析
   
3️⃣ UncertaintyManager
   → 確実性と不確実性を区別

これらを組み合わせることで、
高品質で信頼できる回答が生成できます。
""")
    
    try:
        # 各デモを実行
        demo_knowledge_integrator()
        demo_causal_reasoning_engine()
        demo_uncertainty_manager()
        interactive_demo()
        
        print_section("✅ デモンストレーション完了")
        
        print("""
【学習ポイント】

1. KnowledgeIntegrator:
   - 複数の視点を統合する強力さを実感
   - 矛盾検出の重要性

2. CausalReasoningEngine:
   - 相関と因果の違い
   - 交絡因子の影響
   - 反事実分析の活用

3. UncertaintyManager:
   - 不確実性の定量化
   - 確実性の区分
   - 代替解釈の生成

【次のステップ】

1. コードを読んで実装詳細を理解
   → src/self_improvement/reasoning_engine.py

2. テストケースを実行
   → tests/test_phase7_integration.py

3. 新しいドメインを追加
   → domain_knowledge.py を拡張

4. アルゴリズムを改善
   → より複雑な推論ロジックを実装

【質問がある場合】

1. このデモの出力がわかりにくい部分
2. コードの特定の行をもっと詳しく知りたい
3. 新しいテストケースを追加したい

以上について、質問をお待ちしています！
""")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
