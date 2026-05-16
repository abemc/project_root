---

## ❓ よくある質問（FAQ）

### Q. 各モジュールの役割や関係が分からない場合は？
**A.** 本ドキュメントの「システムアーキテクチャ」や「階層構造図」セクションを参照してください。

### Q. スコア計算やデータ収集の流れが分からない場合は？
**A.** 各層の役割やデータフロー図を確認し、src/agent/autonomy/配下の実装も参照してください。

### Q. モジュール間の連携がうまくいかない場合は？
**A.** モジュールのimportや依存関係、パス設定を見直してください。

---

## ✅ 理解度チェックリスト

- [ ] 各モジュールの役割と関係を説明できる
- [ ] データ収集・スコア計算の流れを説明できる
- [ ] モジュール連携の注意点を説明できる
- [ ] 実装ファイルの場所を説明できる

すべてチェックできたら、次の実践・応用フェーズへ進みましょう！
# autonomy フォルダー モジュール関連性説明書

**作成日**: 2026-04-21  
**バージョン**: 1.0  
**対象**: src/agent/autonomy フレームワーク

---

## 概要

autonomy フォルダーは、**LLMベースエージェントの自律性を定量的に評価する統合フレームワーク** です。3層構造で複数の次元からエージェントの自律性を測定します。

---

## システムアーキテクチャ

### 階層構造図

```
🏗️ 3層アーキテクチャ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

層3: 評価層
┌────────────────────────────────────────────┐
│           AutonomyScorer                   │
│       (総合自律性評価エンジン)               │
│   3つのモジュール → 5次元スコア計算         │
└────────────────────────────────────────────┘
         ↑              ↑              ↑
        (1)            (2)            (3)
         │              │              │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

層2: データ収集層
┌─────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│   TaskTracker   │  │ DecisionAnalyzer   │  │PlanningMeasurer  │
│                 │  │                    │  │                  │
│ タスク成功追跡   │  │  意思決定分析      │  │  計画能力測定    │
│                 │  │                    │  │                  │
│ • 成功/失敗     │  │ • 自律性          │  │ • 計画品質       │
│ • リトライ      │  │ • 品質スコア      │  │ • 段階最適性     │
│ • エラーパターン │  │ • 信頼度          │  │ • リプランニング │
│ • 実行時間      │  │ • 介入率          │  │ • 実行効率       │
└─────────────────┘  └────────────────────┘  └──────────────────┘
         ↑                   ↑                        ↑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

層1: データ源
┌────────────────────────────────────────────────────┐
│         エージェント実行ログ                        │
│                                                    │
│ • タスク実行記録                                   │
│ • 決定履歴・推論ログ                               │
│ • 計画実行ログ・リプランニング履歴                 │
└────────────────────────────────────────────────────┘
```

---

## モジュール詳説

### 1️⃣ TaskTracker - タスク成功追跡

**責務**: エージェントが実行したタスクの成功/失敗を追跡

| 属性 | 説明 |
|------|------|
| **タスク状態** | pending, in_progress, completed, failed, abandoned |
| **タスク種別** | simple, multi_step, complex, reasoning, creative |
| **試行記録** | 試行番号、実行時間、ステップ数、エラー情報 |
| **エラー分類** | logic_error, resource_error, timeout_error, tool_error |
| **復旧追跡** | リトライ回数、復旧試行、最終結果 |

**出力メトリクス**:
- ✅ タスク成功率
- ✅ リトライ効率
- ✅ エラーパターン
- ✅ 実行時間統計

**AutonomyScore への寄与**:
- **goal_achievement** (ゴール達成能力): 重要度 90%

---

### 2️⃣ DecisionAnalyzer - 意思決定分析

**責務**: エージェントの意思決定プロセスを分析し、自律性を測定

| 決定タイプ | 説明 |
|-----------|------|
| **AUTONOMOUS** | 完全に自律的 (ユーザー入力なし) |
| **GUIDED** | ユーザーガイダンスに従った決定 |
| **ESCALATED** | ユーザーへの判断委譲 |
| **FALLBACK** | 代替手段の選択 |

| 品質レベル | スコア | 説明 |
|-----------|--------|------|
| **OPTIMAL** | 1.0 | 最適な決定 |
| **GOOD** | 0.85 | 良好な決定 |
| **ACCEPTABLE** | 0.60 | 許容範囲 |
| **SUBOPTIMAL** | 0.30 | 準最適 |
| **FAILED** | 0.0 | 失敗した決定 |

**出力メトリクス**:
- ✅ 自律性指標 (自律決定の割合)
- ✅ 品質スコア (意思決定品質)
- ✅ ユーザー介入率
- ✅ 平均信頼度

**AutonomyScore への寄与**:
- **decision_independence** (意思決定独立性)
- **error_recovery** (エラー回復能力)

---

### 3️⃣ PlanningMeasurer - 計画能力測定

**責務**: エージェントの計画立案・実行能力を測定

| 計画品質 | 説明 |
|---------|------|
| **OPTIMAL** | 段階が最適で効率的 |
| **GOOD** | 良好な計画 |
| **ACCEPTABLE** | 許容可能な計画 |
| **INEFFICIENT** | 非効率的 |
| **FAILED** | 計画失敗 |

**測定項目**:
- 推定時間 vs 実際の実行時間
- 推定ステップ数 vs 実際のステップ数
- リプランニング回数
- 制約条件への適応

**出力メトリクス**:
- ✅ 計画品質スコア
- ✅ 段階効率
- ✅ リプランニング統計
- ✅ 実行効率

**AutonomyScore への寄与**:
- **strategy_adaptation** (戦略適応性)
- **learning_capability** (学習能力)

---

### 4️⃣ AutonomyScorer - 総合スコア計算エンジン

**責務**: 3つのモジュールからのデータを統合し、5次元の自律性スコアを算出

#### 5次元の自律性スコア

```
自律性スコア = 各次元の加重平均

┌─────────────────────────────────────────┐
│ 1. Goal Achievement (ゴール達成能力)    │ ← TaskTracker
│    目標達成率・タスク完了率              │
│                                         │
│ 2. Decision Independence (意思決定独立性)│ ← DecisionAnalyzer
│    自律決定の割合・介入なしの率          │
│                                         │
│ 3. Error Recovery (エラー回復能力)      │ ← TaskTracker + Analyzer
│    エラー後の復旧率・リトライ効率        │
│                                         │
│ 4. Strategy Adaptation (戦略適応性)    │ ← PlanningMeasurer
│    リプランニング実施率・段階最適性      │
│                                         │
│ 5. Learning Capability (学習能力)      │ ← 全モジュール
│    同型タスク反復成功率・改善トレンド    │
└─────────────────────────────────────────┘

各次元: 0.0 ~ 1.0 (0% ~ 100%)

総合スコア = 0 ~ 100
```

#### 自律性レベル定義

| 総合スコア | レベル | 説明 |
|-----------|--------|------|
| 80-100 | **Autonomous** ⭐⭐⭐ | 完全自律、高品質 |
| 60-79 | **Semi-Autonomous** ⭐⭐ | 十分な自律性 |
| 40-59 | **Guided** ⭐ | ガイダンス必要 |
| 20-39 | **Assisted** | 多大な支援必要 |
| 0-19 | **Non-Autonomous** | ほぼ自動化されていない |

---

## データフロー例

### シナリオ: 日本語テキスト分類タスク

```
【ユーザー入力】
"複数の日本語テキストを感情分析で分類してください"

    ↓
    
┌─────────────────────────────────────────────────┐
│ 📊 TaskTracker が記録                          │
├─────────────────────────────────────────────────┤
│ Task ID: classify_sentiment_001                 │
│ Status: COMPLETED ✅                            │
│ Attempts: 2回                                   │
│   - Attempt 1: FAILED (リソース不足)            │
│   - Attempt 2: COMPLETED ✅                     │
│ Total Duration: 15.3秒                          │
│ Steps Taken: 8ステップ                         │
│ Recovery Attempts: 1回                          │
└─────────────────────────────────────────────────┘

    ↓
    
┌─────────────────────────────────────────────────┐
│ 🤖 DecisionAnalyzer が記録                      │
├─────────────────────────────────────────────────┤
│ Decision 1: テキスト言語判定                    │
│   Type: AUTONOMOUS / Quality: OPTIMAL / Conf: 95%
│                                                 │
│ Decision 2: 分類モデル選択                     │
│   Type: GUIDED / Quality: GOOD / Conf: 88%     │
│   (ユーザーガイドに従用)                        │
│                                                 │
│ Decision 3: 失敗時のリトライ戦略              │
│   Type: AUTONOMOUS / Quality: GOOD / Conf: 92% │
│                                                 │
│ 自律性指標: 67% (2/3が自律)                   │
│ 品質スコア: 82%                                │
│ ユーザー介入率: 33%                            │
└─────────────────────────────────────────────────┘

    ↓
    
┌─────────────────────────────────────────────────┐
│ 📐 PlanningMeasurer が記録                      │
├─────────────────────────────────────────────────┤
│ Plan: 3ステップの実行計画                      │
│ Estimated Time: 10秒                           │
│ Actual Time: 15.3秒 (150% オーバー)            │
│ Estimated Steps: 6ステップ                     │
│ Actual Steps: 8ステップ (133%)                 │
│ Replan Count: 1回 (失敗後の調整)               │
│ Plan Quality: ACCEPTABLE                       │
│ Efficiency: 67%                                │
└─────────────────────────────────────────────────┘

    ↓
    
┌─────────────────────────────────────────────────┐
│ 🎯 AutonomyScorer が統合評価                    │
├─────────────────────────────────────────────────┤
│ 5次元スコア計算:                                │
│                                                 │
│ 1. goal_achievement:                          │
│    85% (2/2完了 - リトライペナルティ)          │
│                                                 │
│ 2. decision_independence:                     │
│    67% (2/3が自律)                            │
│                                                 │
│ 3. error_recovery:                            │
│    100% (失敗から完全に回復)                   │
│                                                 │
│ 4. strategy_adaptation:                       │
│    75% (リプラン実施 + 効率低下)               │
│                                                 │
│ 5. learning_capability:                       │
│    78% (改善トレンド検出)                      │
│                                                 │
│ 総合スコア: 81.0                               │
│ 自律性レベル: Semi-Autonomous ⭐⭐            │
│ 強み: エラー回復能力が優秀                     │
│ 弱み: 計画精度の向上が必要                     │
│ 推奨: 計画段階での時間見積もり精度改善         │
└─────────────────────────────────────────────────┘

    ↓
    
【最終出力】
AutonomyScore オブジェクト:
  - overall_score: 81.0
  - autonomy_level: "Semi-Autonomous"
  - strengths: ["Error Recovery", "Decision Quality"]
  - weaknesses: ["Planning Accuracy", "Resource Efficiency"]
  - recommendations: [
      "時間見積もり精度を改善してください",
      "複数の実行パスを事前に検討してください"
    ]
```

---

## モジュール間の依存関係と連携

### 連携マトリックス

| 連携ポイント | 送信元 | 受信元 | データ | 用途 |
|-------------|--------|--------|--------|------|
| **タスク-決定の連携** | TaskTracker | DecisionAnalyzer | 失敗イベント | どの決定が失敗原因か特定 |
| **計画-実行の連携** | PlanningMeasurer | TaskTracker | 計画情報 | 計画通りの実行か検証 |
| **自律性-品質の関連** | DecisionAnalyzer | AutonomyScorer | 自律性指標 | スコア計算に使用 |
| **失敗回復パターン** | TaskTracker + DecisionAnalyzer | AutonomyScorer | 失敗パターン | 学習能力を評価 |
| **全体統合** | TaskTracker, DecisionAnalyzer, PlanningMeasurer | AutonomyScorer | 全メトリクス | 5次元スコア計算 |

---

## 実装例：統合的な分析フロー

### Python コード例

```python
from src.agent.autonomy import (
    TaskSuccessTracker,
    DecisionAnalyzer,
    PlanningCapacityMeasurer,
    AutonomyScorer,
    TaskStatus,
    DecisionType,
    PlanQuality,
)

# ============================================
# ステップ1: 各モジュールの初期化
# ============================================
task_tracker = TaskSuccessTracker()
decision_analyzer = DecisionAnalyzer()
planning_measurer = PlanningCapacityMeasurer()
scorer = AutonomyScorer()

# ============================================
# ステップ2: タスク実行時にデータを記録
# ============================================

# タスク記録
task_tracker.add_attempt(
    task_id="search_001",
    status=TaskStatus.COMPLETED,
    start_time="2026-04-21T10:00:00",
    end_time="2026-04-21T10:00:45",
    duration=45.2,
    steps_taken=12,
    recovery_attempts=1  # 1回失敗からの復旧
)

# 決定記録
flow = decision_analyzer.create_flow(
    task_id="search_001",
    task_description="クエリの意図分析"
)

step1 = decision_analyzer.record_decision(
    flow=flow,
    decision_type=DecisionType.AUTONOMOUS,
    context="クエリ分析",
    options=["entity_search", "concept_search"],
    selected="entity_search",
    reasoning="固有表現が明示的",
    confidence=0.95,
)

decision_analyzer.evaluate_step_quality(step1, actual_outcome=True)
decision_analyzer.complete_flow(flow, overall_success=True)

# 計画記録
plan = planning_measurer.create_plan(
    plan_id="plan_001",
    task_description="検索実行計画"
)

planning_measurer.add_step(
    plan=plan,
    step_number=1,
    description="クエリ準備",
    estimated_duration=5.0
)
planning_measurer.execute_step(
    plan=plan,
    step_number=1,
    actual_duration=4.8,
    success=True
)

plan.total_actual_time = 45.2
planning_measurer.measure_execution(
    plan=plan,
    replan_count=1,
    plan_quality=PlanQuality.GOOD
)

# ============================================
# ステップ3: AutonomyScorer で統合評価
# ============================================

autonomy_score = scorer.calculate_score(
    task_metrics=task_tracker.get_metrics(),
    decision_metrics=decision_analyzer.get_metrics(),
    planning_metrics=planning_measurer.get_metrics()
)

# ============================================
# ステップ4: 結果の確認
# ============================================

print(f"総合スコア: {autonomy_score.overall_score:.1f}")
print(f"自律性レベル: {autonomy_score.autonomy_level}")
print(f"強み: {', '.join(autonomy_score.strengths)}")
print(f"弱み: {', '.join(autonomy_score.weaknesses)}")
print(f"推奨: {', '.join(autonomy_score.recommendations)}")

# 出力例:
# 総合スコア: 81.0
# 自律性レベル: Semi-Autonomous
# 強み: Error Recovery, High Quality Decisions
# 弱み: Planning Accuracy
# 推奨: Improve time estimation accuracy, Consider multiple execution paths
```

---

## モジュール間のデータ構造

### データ流入先と形式

```
【TaskTracker のメトリクス出力】
{
    "total_tasks": 10,
    "completed": 8,
    "failed": 2,
    "success_rate": 0.80,           ← goal_achievement に
    "avg_retry_count": 1.2,
    "error_distribution": {...},
    "avg_duration": 45.2,
    "recovery_success_rate": 0.95   ← error_recovery に
}

    ↓

【DecisionAnalyzer のメトリクス出力】
{
    "total_decisions": 15,
    "autonomous_count": 10,
    "autonomy_score": 0.67,         ← decision_independence に
    "avg_quality": 0.82,
    "avg_confidence": 0.88,
    "intervention_rate": 0.33,
    "error_recovery_decisions": 3   ← error_recovery に
}

    ↓

【PlanningMeasurer のメトリクス出力】
{
    "total_plans": 5,
    "plan_quality_scores": [0.75, 0.80, ...],
    "replan_count": 2,
    "adaptation_score": 0.78,       ← strategy_adaptation に
    "learning_trend": 0.15,         ← learning_capability に
    "efficiency_avg": 0.85
}

    ↓

【AutonomyScorer の統合結果】
AutonomyScore {
    "overall_score": 79.5,
    "autonomy_level": "Semi-Autonomous",
    "dimensions": {
        "goal_achievement": 0.80,
        "decision_independence": 0.67,
        "error_recovery": 0.95,
        "strategy_adaptation": 0.78,
        "learning_capability": 0.80
    },
    "strengths": ["Error Recovery", "Goal Achievement"],
    "weaknesses": ["Decision Independence"],
    "recommendations": ["Increase autonomous decisions", "Improve planning"]
}
```

---

## ファイル構成と行数

| ファイル | 行数 | 責務 |
|---------|------|------|
| `autonomy_scorer.py` | ~400行 | 総合スコア計算 |
| `decision_analyzer.py` | 606行 | 意思決定分析 ✅ (新実装) |
| `planning_measurer.py` | ~350行 | 計画能力測定 |
| `task_tracker.py` | ~400行 | タスク成功追跡 |
| `examples.py` | 318行 | 使用例・デモ ✅ (新実装) |
| `__init__.py` | ~50行 | パッケージ初期化 |
| **合計** | **~2,100行** | — |

---

## まとめ

### 3つの重要な特徴

1. **モジュール独立性** 📦
   - 各モジュールは独立して動作可能
   - 個別のデータ収集が可能
   - 疎結合設計

2. **統合評価** 🎯
   - AutonomyScorer が3つのモジュールを統合
   - 複数次元での評価により、エージェント能力の全体像を把握
   - スコアに基づく改善指針を自動生成

3. **拡張性** 🚀
   - 新しい次元の追加が容易
   - 既存モジュールの拡張が可能
   - 他システムとの統合が容易

### 活用シーン

- ✅ エージェント能力の継続的監視
- ✅ 改善施策の効果測定
- ✅ パフォーマンス比較
- ✅ 問題診断と最適化
- ✅ ユーザーへの能力説明

---

**更新日**: 2026-04-21  
**関連ドキュメント**:
- [AGENT_AUTONOMY_ANALYSIS.md](AGENT_AUTONOMY_ANALYSIS.md) - DecisionAnalyzer 詳細
- [PHASE12_AUTONOMY_COMPLETION_REPORT.md](../PHASE12_AUTONOMY_COMPLETION_REPORT.md) - Phase 12 完成レポート
