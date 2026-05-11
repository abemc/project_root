"""
エージェント自律性分析 - 使用例

エージェント意思決定フロー分析システムの実装例。
"""

import sys
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agent.autonomy.decision_analyzer import (
    DecisionAnalyzer,
    DecisionType,
)


def example_basic_usage():
    """基本的な使用例"""
    print("=" * 60)
    print("例1: 基本的な使用方法")
    print("=" * 60)
    
    # 分析器を初期化
    analyzer = DecisionAnalyzer()
    
    # タスク: 検索クエリの最適化
    flow = analyzer.create_flow(
        task_id="search_001",
        task_description="検索クエリの最適化処理"
    )
    
    # ステップ1: クエリ解析戦略の選択
    step1 = analyzer.record_decision(
        flow=flow,
        decision_type=DecisionType.AUTONOMOUS,
        context="検索クエリの言語分析",
        options=["形態素解析", "単純分割"],
        selected="形態素解析",
        reasoning="日本語テキスト最適化のため",
        confidence=0.95,
    )
    
    # ステップの品質を評価（結果が判明後）
    analyzer.evaluate_step_quality(step1, actual_outcome=True)
    
    # ステップ2: インデックス選択
    step2 = analyzer.record_decision(
        flow=flow,
        decision_type=DecisionType.AUTONOMOUS,
        context="検索インデックスの選択",
        options=["semantic_index", "keyword_index"],
        selected="semantic_index",
        reasoning="意味ベースの検索が効果的",
        confidence=0.92,
    )
    analyzer.evaluate_step_quality(step2, actual_outcome=True)
    
    # フロー完了
    analyzer.complete_flow(flow, overall_success=True)
    
    # メトリクスを取得
    print("\n【自律性メトリクス】")
    autonomy = analyzer.get_autonomy_metrics()
    for key, value in autonomy.items():
        print(f"  {key}: {value:.2%}" if isinstance(value, float) else f"  {key}: {value}")
    
    print("\n【品質メトリクス】")
    quality = analyzer.get_decision_quality_metrics()
    for key, value in quality.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.2%}")
        else:
            print(f"  {key}: {value:.2%}")


def example_mixed_decisions():
    """自律/ガイド付き/エスカレーション混合の例"""
    print("\n" + "=" * 60)
    print("例2: 複雑な意思決定フロー")
    print("=" * 60)
    
    analyzer = DecisionAnalyzer()
    
    # タスク: ドキュメント検索
    flow = analyzer.create_flow(
        task_id="doc_search_001",
        task_description="複雑なドキュメント検索"
    )
    
    # ステップ1: 自律決定（クエリ分析）
    step1 = analyzer.record_decision(
        flow=flow,
        decision_type=DecisionType.AUTONOMOUS,
        context="クエリの意図分析",
        options=["entity_search", "concept_search"],
        selected="entity_search",
        reasoning="固有表現が明示的に含まれている",
        confidence=0.88,
    )
    analyzer.evaluate_step_quality(step1, actual_outcome=False)
    
    # ステップ2: ガイド付き決定（リトライ戦略）
    step2 = analyzer.record_decision(
        flow=flow,
        decision_type=DecisionType.GUIDED,
        context="検索戦略の修正",
        options=["retry_with_expansion", "fallback_keyword", "escalate"],
        selected="retry_with_expansion",
        reasoning="ユーザーガイダンスに基づき拡張検索を試行",
        confidence=0.75,
        user_intervention=True,
    )
    analyzer.evaluate_step_quality(step2, actual_outcome=True)
    
    # ステップ3: エスカレーション
    step3 = analyzer.record_decision(
        flow=flow,
        decision_type=DecisionType.ESCALATED,
        context="複雑な検索クエリ",
        options=["manual_review", "agent_escalation"],
        selected="agent_escalation",
        reasoning="ユーザーに複数オプションを提示",
        confidence=0.7,
    )
    analyzer.evaluate_step_quality(step3, actual_outcome=True)
    
    analyzer.complete_flow(flow, overall_success=True)
    
    # 詳細サマリー
    summary = analyzer.export_flow_summary(flow)
    print("\n【フロー詳細サマリー】")
    print(f"  タスク: {summary['task_description']}")
    print(f"  成功: {summary['success']}")
    print(f"  ステップ数: {summary['step_count']}")
    print(f"  自律性スコア: {summary['autonomy_score']:.2%}")
    print(f"  品質スコア: {summary['quality_score']:.2%}")
    print(f"  ユーザー介入率: {summary['intervention_rate']:.2%}")
    print(f"  平均信頼度: {summary['average_confidence']:.2%}")


def example_failure_analysis():
    """失敗パターン分析の例"""
    print("\n" + "=" * 60)
    print("例3: 失敗パターン分析")
    print("=" * 60)
    
    analyzer = DecisionAnalyzer()
    
    # 失敗フロー1: 過信による失敗
    flow1 = analyzer.create_flow("task_001", "高信頼度での失敗ケース")
    step1 = analyzer.record_decision(
        flow=flow1,
        decision_type=DecisionType.AUTONOMOUS,
        context="リスク判定",
        options=["safe", "risky"],
        selected="safe",
        reasoning="パターン認識に基づいて判定",
        confidence=0.98,
    )
    analyzer.evaluate_step_quality(step1, actual_outcome=False)
    analyzer.complete_flow(flow1, overall_success=False)
    
    # 失敗フロー2: 過度なエスカレーション
    flow2 = analyzer.create_flow("task_002", "エスカレーション多発ケース")
    for i in range(5):
        step = analyzer.record_decision(
            flow=flow2,
            decision_type=DecisionType.ESCALATED,
            context=f"判断{i+1}",
            options=["A", "B"],
            selected="A",
            reasoning="確実性が低いため",
            confidence=0.5 + i*0.02,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=(i % 2 == 0))
    analyzer.complete_flow(flow2, overall_success=False)
    
    # 成功フロー（対比用）
    flow3 = analyzer.create_flow("task_003", "自律的成功ケース")
    for i in range(3):
        step = analyzer.record_decision(
            flow=flow3,
            decision_type=DecisionType.AUTONOMOUS,
            context=f"判断{i+1}",
            options=["A", "B"],
            selected="A",
            reasoning="明確な根拠がある",
            confidence=0.85 + i*0.05,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=True)
    analyzer.complete_flow(flow3, overall_success=True)
    
    # パターン分析
    print("\n【失敗パターン分析】")
    failures = analyzer.analyze_failure_patterns()
    print(f"  失敗率: {failures['failure_rate']:.2%}")
    print(f"  総失敗フロー数: {failures['total_failures']}")
    print(f"  総フロー数: {failures['total_flows']}")
    
    print("\n【リスクパターン検出】")
    risks = analyzer.detect_risk_patterns()
    print(f"  高信頼度での失敗: {len(risks['high_confidence_failures'])}件")
    print(f"  過度なエスカレーション: {len(risks['excessive_escalations'])}件")
    
    print("\n【決定チェーン分析】")
    chains = analyzer.analyze_decision_chains()
    print(f"  ユニークなチェーン数: {chains['total_unique_chains']}")
    for chain, info in list(chains['chains'].items())[:3]:
        print(f"    {chain}")
        print(f"      出現回数: {info['count']}, 成功率: {info['success_rate']:.2%}")


def example_report_generation(output_dir: Path = Path("/tmp")):
    """レポート生成と エクスポートの例"""
    print("\n" + "=" * 60)
    print("例4: レポート生成とエクスポート")
    print("=" * 60)
    
    analyzer = DecisionAnalyzer()
    
    # 複数のタスクを処理
    for task_num in range(1, 4):
        flow = analyzer.create_flow(
            task_id=f"batch_task_{task_num:03d}",
            task_description=f"バッチ処理タスク {task_num}"
        )
        
        # ステップを記録
        for step_num in range(1, 3):
            step = analyzer.record_decision(
                flow=flow,
                decision_type=DecisionType.AUTONOMOUS,
                context=f"処理ステップ{step_num}",
                options=["optionA", "optionB"],
                selected="optionA",
                reasoning="統計的に最適",
                confidence=0.85 + step_num * 0.03,
            )
            analyzer.evaluate_step_quality(step, actual_outcome=task_num % 2 == 0)
        
        # フロー完了
        analyzer.complete_flow(flow, overall_success=task_num % 2 == 0)
    
    # 総合レポートを生成
    report = analyzer.generate_autonomy_report()
    
    print("\n【総合レポート】")
    print(f"  生成日時: {report['timestamp']}")
    print(f"  総合自律性スコア: {report['autonomy_score']:.2%}")
    
    print("\n【統計サマリー】")
    summary = report['summary']
    print(f"  処理タスク数: {summary['total_tasks']}")
    print(f"  全体成功率: {summary['overall_success_rate']:.2%}")
    print(f"  平均自律性: {summary['average_autonomy']:.2%}")
    print(f"  平均品質スコア: {summary['average_quality']:.2%}")
    print(f"  ユーザー介入率: {summary['intervention_rate']:.2%}")
    print(f"  失敗率: {summary['failure_rate']:.2%}")
    
    # ファイルにエクスポート
    output_dir.mkdir(exist_ok=True)
    
    json_file = output_dir / "autonomy_report.json"
    csv_flows = output_dir / "flows.csv"
    csv_steps = output_dir / "steps.csv"
    
    analyzer.export_to_json(json_file)
    analyzer.export_flows_to_csv(csv_flows)
    analyzer.export_steps_to_csv(csv_steps)
    
    print("\n【エクスポート完了】")
    print(f"  JSON レポート: {json_file}")
    print(f"  フロー CSV: {csv_flows}")
    print(f"  ステップ CSV: {csv_steps}")


def example_print_summary():
    """コンソール出力例"""
    print("\n" + "=" * 60)
    print("例5: コンソール出力")
    print("=" * 60)
    
    analyzer = DecisionAnalyzer()
    
    # 複数の処理
    for i in range(3):
        flow = analyzer.create_flow(f"task_{i:03d}", f"テストタスク {i+1}")
        step = analyzer.record_decision(
            flow=flow,
            decision_type=DecisionType.AUTONOMOUS,
            context="テスト処理",
            options=["A", "B"],
            selected="A",
            reasoning="テスト",
            confidence=0.85,
        )
        analyzer.evaluate_step_quality(step, actual_outcome=True)
        analyzer.complete_flow(flow, overall_success=True)
    
    # コンソールに出力
    analyzer.print_summary()


if __name__ == "__main__":
    example_basic_usage()
    example_mixed_decisions()
    example_failure_analysis()
    example_report_generation()
    example_print_summary()
    
    print("\n" + "=" * 60)
    print("すべての例が完了しました")
    print("=" * 60)
