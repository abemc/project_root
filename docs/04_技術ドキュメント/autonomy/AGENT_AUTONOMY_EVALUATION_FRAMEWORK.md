# エージェント自律性評価フレームワーク

**バージョン**: 1.0  
**作成日**: 2025年4月  
**ステータス**: ✅ 完成・実装済み

---

## 📋 概要

このフレームワークは、**LLMベースエージェントの自律性を定量的に評価**するための包括的なシステムです。エージェントが人間の介入なしにどの程度独立して機能できるかを、複数の次元から測定します。

### 🎯 主要な評価次元

| 次元 | 説明 | 重み | 目標値 |
|------|------|------|--------|
| **ゴール達成能力** | タスク成功率 | 30% | 90%+ |
| **意思決定独立性** | ユーザー介入なしの決定率 | 25% | 80%+ |
| **エラー回復能力** | エラーからの自動回復率 | 20% | 85%+ |
| **戦略適応性** | 状況に応じた戦略変更能力 | 15% | 70%+ |
| **学習能力** | 試行を通じた改善能力 | 10% | 60%+ |

---

## 🏗️ フレームワーク構成

### モジュール構成図

```
src/agent/autonomy/
├── __init__.py                    # モジュールエクスポート
├── autonomy_scorer.py             # 自律性スコア計算
├── decision_analyzer.py            # 意思決定分析
├── planning_measurer.py            # 計画能力測定
├── task_tracker.py                 # タスク追跡
└── examples.py                     # 使用例
```

### 5つの主要コンポーネント

#### 1️⃣ **自律性スコアリングエンジン** (`autonomy_scorer.py`)

**責務**: 複数指標から総合的な自律性スコアを計算

**主要クラス**:
```python
class DimensionalAutonomy:
    """各次元における自律性スコア"""
    goal_achievement: float           # ゴール達成能力 (0-1)
    decision_independence: float      # 意思決定独立性 (0-1)
    error_recovery: float             # エラー回復能力 (0-1)
    strategy_adaptation: float        # 戦略適応性 (0-1)
    learning_capability: float        # 学習能力 (0-1)

class AutonomyScore:
    """総合評価スコア"""
    dimensions: DimensionalAutonomy   # 各次元スコア
    overall_score: float              # 総合スコア (0-100)
    autonomy_level: str               # 自律性レベル
    strengths: List[str]              # 強み
    weaknesses: List[str]             # 弱み
    recommendations: List[str]        # 改善推奨

class AutonomyScorer:
    """スコアリングエンジン"""
    def calculate_score(...) -> AutonomyScore
    def get_improvement_trend() -> Optional[float]
    def get_average_score() -> Optional[float]
```

**自律性レベルの定義**:
- 🟢 **Autonomous** (80-100): 完全自律
- 🟡 **Semi-Autonomous** (60-79): 半自律
- 🟠 **Guided** (40-59): ガイド付き
- 🔴 **Assisted** (20-39): 支援的
- ⚫ **Dependent** (0-19): 依存的

**計算例**:
```python
scorer = AutonomyScorer()
score = scorer.calculate_score(
    task_success_rate=0.95,      # 95%成功
    user_intervention_rate=0.10,  # 10%ユーザー介入
    error_recovery_rate=0.90,     # 90%エラー回復
    strategy_switches=3,          # 3回の戦略変更
    learning_rate=0.15,           # 15%の学習率
    total_attempts=20
)
# 結果: Autonomous (85点)
```

---

#### 2️⃣ **意思決定フロー分析** (`decision_analyzer.py`)

**責務**: エージェントの意思決定プロセスを追跡・分析

**主要クラス**:
```python
class DecisionType(Enum):
    AUTONOMOUS = "autonomous"      # 完全自律
    GUIDED = "guided"             # ガイド付き
    ESCALATED = "escalated"       # エスカレーション
    FALLBACK = "fallback"         # フォールバック

class DecisionQuality(Enum):
    OPTIMAL = "optimal"           # 最適
    GOOD = "good"                # 良好
    ACCEPTABLE = "acceptable"    # 許容
    SUBOPTIMAL = "suboptimal"    # 準最適
    FAILED = "failed"            # 失敗

class DecisionStep:
    """単一の意思決定ステップ"""
    step_id: int
    decision_type: DecisionType
    context: str                  # 決定コンテキスト
    options_considered: List[str] # 検討した選択肢
    selected_option: str          # 選択された選択肢
    reasoning: str                # 意思決定理由
    confidence: float             # 信頼度 (0-1)
    quality: DecisionQuality      # 品質評価
    user_intervention: bool       # ユーザー介入が必要か

class DecisionFlow:
    """一連の意思決定フロー"""
    task_id: str
    task_description: str
    steps: List[DecisionStep]
    overall_success: bool
    
    def add_step(step: DecisionStep) -> None
    def get_autonomy_score() -> float
    def analyze_decision_patterns() -> Dict

class DecisionAnalyzer:
    """意思決定分析エンジン"""
    def analyze_flow(flow: DecisionFlow) -> Dict
    def generate_report(flows: List[DecisionFlow]) -> Dict
    def export_to_csv(flows: List[DecisionFlow], path: str) -> None
```

**分析機能**:
- ✅ 自律決定の割合
- ✅ 意思決定の論理性評価
- ✅ ユーザー介入の必要性検出
- ✅ 決定品質の自動評価

**使用例**:
```python
# 意思決定フローを記録
flow = DecisionFlow(task_id="task_001", task_description="ユーザークエリ処理")

step = DecisionStep(
    step_id=1,
    decision_type=DecisionType.AUTONOMOUS,
    context="ユーザーが情報検索リクエスト",
    options_considered=["検索エンジン使用", "ナレッジベース検索", "外部API"],
    selected_option="検索エンジン使用",
    reasoning="最も包括的な結果が期待できる",
    confidence=0.92,
    user_intervention=False
)
flow.add_step(step)

# 分析
analyzer = DecisionAnalyzer()
report = analyzer.analyze_flow(flow)
```

---

#### 3️⃣ **計画能力測定** (`planning_measurer.py`)

**責務**: エージェントの計画立案・実行能力を測定

**主要クラス**:
```python
class PlanStep:
    """計画内のステップ"""
    step_number: int
    description: str
    dependencies: List[int]        # 依存するステップID
    estimated_tokens: int          # 予想トークン数
    actual_tokens: int             # 実際のトークン数
    status: str                    # 実行ステータス
    success: bool                  # 成功フラグ

class ExecutionPlan:
    """実行計画全体"""
    plan_id: str
    goal: str
    steps: List[PlanStep]
    creation_timestamp: str
    execution_start: Optional[str]
    execution_end: Optional[str]
    total_tokens_allocated: int
    total_tokens_used: int
    
    def add_step(step: PlanStep) -> None
    def mark_step_complete(step_id: int, success: bool) -> None
    def get_completion_rate() -> float
    def get_token_efficiency() -> float

class PlanningCapacityMeasurer:
    """計画能力測定エンジン"""
    def create_plan(goal: str, steps: List[PlanStep]) -> ExecutionPlan
    def execute_step(plan_id: str, step_id: int, ...) -> bool
    def measure_planning_efficiency() -> Dict
    def analyze_adaptation() -> Dict
```

**測定指標**:
- ✅ 計画の完成度 (0-1)
- ✅ ステップの論理性 (0-1)
- ✅ トークン効率性 (実際/予想)
- ✅ 適応能力 (計画変更の適切性)
- ✅ 完了率

**使用例**:
```python
measurer = PlanningCapacityMeasurer()

# 計画を作成
plan = ExecutionPlan(
    plan_id="plan_001",
    goal="複雑なデータ分析レポート作成"
)

# ステップを追加
step1 = PlanStep(step_number=1, description="データ取得", estimated_tokens=500)
step2 = PlanStep(step_number=2, description="データ前処理", estimated_tokens=1000)
step3 = PlanStep(step_number=3, description="分析", estimated_tokens=2000)

plan.add_step(step1)
plan.add_step(step2)
plan.add_step(step3)

# 実行と測定
measurer.execute_step(plan.plan_id, 1, actual_tokens=480, success=True)
efficiency = measurer.measure_planning_efficiency()
```

---

#### 4️⃣ **タスク追跡システム** (`task_tracker.py`)

**責務**: エージェントのタスク実行を追跡・分析

**主要クラス**:
```python
class TaskAttempt:
    """単一のタスク試行"""
    attempt_number: int
    status: str                   # "pending", "in_progress", "completed", "failed"
    started_at: str
    completed_at: Optional[str]
    tokens_used: int
    success: bool
    error_message: Optional[str]
    duration_seconds: Optional[float]

class TaskRecord:
    """タスク全体の記録"""
    task_id: str
    description: str
    category: str                 # "research", "analysis", "generation"等
    attempts: List[TaskAttempt]
    first_attempt_success: bool
    retry_count: int
    avg_duration: float
    total_tokens: int
    success_rate: float           # 成功率 (0-1)
    
    def add_attempt(attempt: TaskAttempt) -> None
    def mark_as_complete(success: bool) -> None

class TaskSuccessTracker:
    """タスク成功追跡エンジン"""
    def create_task(task_id: str, description: str) -> TaskRecord
    def record_attempt(task_id: str, attempt: TaskAttempt) -> None
    def get_success_metrics() -> Dict
    def generate_task_report() -> Dict
    def get_trending_improvement() -> Optional[float]
```

**追跡指標**:
- ✅ 初回試行成功率
- ✅ 総合成功率
- ✅ 再試行回数
- ✅ 平均実行時間
- ✅ トークン効率

**使用例**:
```python
tracker = TaskSuccessTracker()

# タスク作成
task = tracker.create_task(
    task_id="task_001",
    description="複雑なコード生成"
)

# 試行1
attempt1 = TaskAttempt(
    attempt_number=1,
    started_at=datetime.now().isoformat(),
    tokens_used=2500,
    success=False,
    error_message="構文エラー"
)
tracker.record_attempt("task_001", attempt1)

# 試行2
attempt2 = TaskAttempt(
    attempt_number=2,
    started_at=datetime.now().isoformat(),
    tokens_used=3000,
    success=True
)
tracker.record_attempt("task_001", attempt2)

# レポート
report = tracker.get_success_metrics()
```

---

#### 5️⃣ **統合評価エンジン** (統合機能)

**統合API**:
```python
from src.agent.autonomy import (
    AutonomyScorer,
    DecisionAnalyzer,
    PlanningCapacityMeasurer,
    TaskSuccessTracker,
)

# 1. スコア計算
scorer = AutonomyScorer()
score = scorer.calculate_score(...)

# 2. 意思決定分析
analyzer = DecisionAnalyzer()
decision_report = analyzer.analyze_flow(flow)

# 3. 計画測定
measurer = PlanningCapacityMeasurer()
plan_metrics = measurer.measure_planning_efficiency()

# 4. タスク追跡
tracker = TaskSuccessTracker()
task_metrics = tracker.get_success_metrics()
```

---

## 💡 使用シナリオ

### シナリオ1: 新しいエージェントのベースライン評価

```python
from src.agent.autonomy import AutonomyScorer

# エージェント初期化
agent = MyAgent()

# 5つのテストタスク実行
results = {
    "success_rate": 0.92,
    "intervention_rate": 0.15,
    "recovery_rate": 0.88,
    "strategy_changes": 2,
    "learning_improvement": 0.12
}

scorer = AutonomyScorer()
baseline_score = scorer.calculate_score(
    task_success_rate=results["success_rate"],
    user_intervention_rate=results["intervention_rate"],
    error_recovery_rate=results["recovery_rate"],
    strategy_switches=results["strategy_changes"],
    learning_rate=results["learning_improvement"]
)

print(f"Baseline Score: {baseline_score.overall_score:.1f}")
print(f"Level: {baseline_score.autonomy_level}")
print(f"Strengths: {baseline_score.strengths}")
print(f"Recommendations: {baseline_score.recommendations}")
```

### シナリオ2: 継続的な改善追跡

```python
from src.agent.autonomy import AutonomyScorer

scorer = AutonomyScorer()

# 週1回のスコアリング（4週間）
for week in range(1, 5):
    metrics = get_weekly_metrics(agent, week)
    
    score = scorer.calculate_score(**metrics)
    print(f"Week {week}: {score.overall_score:.1f} ({score.autonomy_level})")

# 改善傾向を取得
improvement = scorer.get_improvement_trend()
print(f"Improvement: {improvement:.1f}%")
```

### シナリオ3: 意思決定品質の詳細分析

```python
from src.agent.autonomy import DecisionAnalyzer, DecisionFlow

analyzer = DecisionAnalyzer()

# エージェント実行を記録
flow = record_agent_execution(agent, task)

# 分析
analysis = analyzer.analyze_flow(flow)

# レポート出力
report = analyzer.generate_report([flow])
print(report)

# CSV出力
analyzer.export_to_csv([flow], "decision_analysis.csv")
```

### シナリオ4: 計画能力の評価

```python
from src.agent.autonomy import PlanningCapacityMeasurer

measurer = PlanningCapacityMeasurer()

# エージェントに複雑なタスクを実行
plan = agent.create_plan(complex_task)

# 計画を測定エンジンに登録
measured_plan = measurer.create_plan(
    plan.goal,
    plan.steps
)

# 実行
for i, step in enumerate(plan.steps):
    result = agent.execute_step(step)
    measurer.execute_step(
        measured_plan.plan_id,
        i,
        actual_tokens=result.tokens,
        success=result.success
    )

# 効率性を測定
efficiency = measurer.measure_planning_efficiency()
print(f"Planning Efficiency: {efficiency}")
```

### シナリオ5: タスク成功率の段階的追跡

```python
from src.agent.autonomy import TaskSuccessTracker

tracker = TaskSuccessTracker()

# 複数のタスクを実行
for task_definition in tasks:
    task = tracker.create_task(task_definition["id"], task_definition["desc"])
    
    # 1回目の試行
    attempt1 = run_attempt(agent, task)
    tracker.record_attempt(task.task_id, attempt1)
    
    # 失敗した場合は再試行
    if not attempt1.success:
        attempt2 = run_attempt(agent, task)
        tracker.record_attempt(task.task_id, attempt2)

# 成功メトリクスを取得
metrics = tracker.get_success_metrics()
print(f"Overall Success Rate: {metrics['overall_success_rate']:.1%}")
print(f"First Attempt Success: {metrics['first_attempt_success_rate']:.1%}")
print(f"Trending Improvement: {metrics['trending_improvement']:.1%}")
```

---

## 📊 出力とレポート

### スコアレポート例

```
================================================================================
                    AUTONOMY EVALUATION REPORT
================================================================================

Agent Name: Research Assistant v2.1
Evaluation Date: 2025-04-21
Test Duration: 7 days

OVERALL SCORE: 82.5 / 100  [AUTONOMOUS]

DIMENSIONAL SCORES:
  ✓ Goal Achievement:      0.92 (91%)  [EXCELLENT]
  ✓ Decision Independence: 0.85 (85%)  [GOOD]
  ✓ Error Recovery:        0.88 (88%)  [GOOD]
  ✓ Strategy Adaptation:   0.76 (76%)  [ACCEPTABLE]
  ✓ Learning Capability:   0.68 (68%)  [ACCEPTABLE]

STRENGTHS:
  • Goal Achievement: 92%
  • Error Recovery: 88%
  • Decision Independence: 85%

AREAS FOR IMPROVEMENT:
  • Strategy Adaptation: 76%
  • Learning Capability: 68%

RECOMMENDATIONS:
  1. 状況に応じた戦略変更ロジックを強化してください
  2. 過去の経験から学習するメカニズムを改善してください
  3. 新しいドメインでの応用可能性を探索してください

IMPROVEMENT TREND:
  Week 1: 78.0  →  Week 2: 80.5  →  Week 3: 81.8  →  Week 4: 82.5
  成長率: +5.8% (4週間平均)

EVALUATION HISTORY:
  Total Evaluations: 4
  Average Score: 80.7
  Best Score: 82.5 (Latest)

================================================================================
```

### 意思決定フロー分析レポート

```
DECISION FLOW ANALYSIS
Task: "Complex Data Analysis"

AUTONOMY BREAKDOWN:
  Autonomous Decisions:       85% (17/20 steps)
  Guided Decisions:            10% (2/20 steps)
  Escalated Decisions:         5% (1/20 steps)

DECISION QUALITY:
  Optimal Decisions:           70%
  Good Decisions:              20%
  Acceptable Decisions:        10%
  Failed Decisions:            0%

USER INTERVENTION:
  Required: 1 time (5%)
  Reason: Decision confidence < 0.60

CONFIDENCE DISTRIBUTION:
  High (0.8+):   80%
  Medium (0.6-0.8): 15%
  Low (<0.6):    5%
```

---

## 🔧 高度な使用方法

### カスタム加重設定

```python
from src.agent.autonomy import AutonomyScorer, AutonomyDimension

scorer = AutonomyScorer()

# 研究タスク向けのカスタム加重
research_weights = {
    AutonomyDimension.GOAL_ACHIEVEMENT: 0.35,      # より重要
    AutonomyDimension.DECISION_INDEPENDENCE: 0.20,
    AutonomyDimension.ERROR_RECOVERY: 0.15,
    AutonomyDimension.STRATEGY_ADAPTATION: 0.20,   # より重要
    AutonomyDimension.LEARNING_CAPABILITY: 0.10,
}

scorer.DIMENSION_WEIGHTS = research_weights
score = scorer.calculate_score(...)
```

### ベンチマーク比較

```python
from src.agent.autonomy import AutonomyScorer

scorers = {
    "Agent A": AutonomyScorer(),
    "Agent B": AutonomyScorer(),
    "Agent C": AutonomyScorer(),
}

# 各エージェントを評価
for name, scorer in scorers.items():
    score = scorer.calculate_score(...)
    print(f"{name}: {score.overall_score:.1f} ({score.autonomy_level})")

# 比較表を作成
comparison = {name: scorer.get_average_score() for name, scorer in scorers.items()}
```

### 動的しきい値設定

```python
class AdaptiveAutonomyScorer(AutonomyScorer):
    def __init__(self, task_category: str):
        super().__init__()
        self.task_category = task_category
        self._adjust_thresholds()
    
    def _adjust_thresholds(self):
        """タスク種別に応じてしきい値を調整"""
        if self.task_category == "safety_critical":
            self.LEVEL_DEFINITIONS["Autonomous"] = (90, 100)  # より厳しく
        elif self.task_category == "exploration":
            self.LEVEL_DEFINITIONS["Autonomous"] = (70, 100)  # より緩く
```

---

## 📈 主要なメトリクス定義

### ゴール達成能力
```
Definition: タスク成功率 (0-1)
Formula: (成功したタスク数) / (総タスク数)
Target: 0.90+
Measurement: 実行結果の自動確認
```

### 意思決定独立性
```
Definition: ユーザー介入なしの決定率 (0-1)
Formula: (介入不要な決定数) / (総決定数)
Target: 0.80+
Measurement: ユーザー介入イベントの記録
```

### エラー回復能力
```
Definition: エラーから自動回復した率 (0-1)
Formula: (自動回復したエラー数) / (総エラー数)
Target: 0.85+
Measurement: エラーハンドリングログの分析
```

### 戦略適応性
```
Definition: 状況に応じた戦略変更の適切性 (0-1)
Formula: 変更回数が最適範囲内か評価
Target: 0.70+
Measurement: 戦略変更の効果測定
```

### 学習能力
```
Definition: 試行を通じた改善率 (0-1)
Formula: (最終パフォーマンス - 初期) / 初期
Target: 0.60+
Measurement: パフォーマンス改善の時系列データ
```

---

## 🚀 ベストプラクティス

### 1. 定期的な評価
- **推奨頻度**: 週1回以上
- **理由**: パフォーマンス変化を検出
- **実装**: 自動スケジューリング

### 2. 複数メトリクスの組み合わせ
- 単一メトリクスに依存しない
- 複数の視点から評価
- コンテキストに応じた加重

### 3. 過去データとの比較
```python
# 改善傾向の追跡
improvement = scorer.get_improvement_trend()
if improvement > 5:  # 5%以上の改善
    print("Significant improvement detected")
```

### 4. ドメイン固有の調整
```python
# 医療ドメイン: 信頼性重視
if domain == "medical":
    weights[GOAL_ACHIEVEMENT] = 0.40
    weights[ERROR_RECOVERY] = 0.30
```

### 5. 継続的な改善ループ
```
評価 → 分析 → 推奨 → 改善 → 再評価
```

---

## 📚 API リファレンス

### AutonomyScorer

```python
class AutonomyScorer:
    def calculate_score(
        task_success_rate: float,
        user_intervention_rate: float,
        error_recovery_rate: float,
        strategy_switches: int,
        learning_rate: float,
        total_attempts: int = 1,
    ) -> AutonomyScore

    def get_improvement_trend() -> Optional[float]
    def get_average_score() -> Optional[float]
    def reset_history() -> None
```

### DecisionAnalyzer

```python
class DecisionAnalyzer:
    def analyze_flow(flow: DecisionFlow) -> Dict
    def generate_report(flows: List[DecisionFlow]) -> Dict
    def export_to_csv(flows: List[DecisionFlow], path: str) -> None
```

### PlanningCapacityMeasurer

```python
class PlanningCapacityMeasurer:
    def create_plan(goal: str, steps: List[PlanStep]) -> ExecutionPlan
    def execute_step(plan_id: str, step_id: int, ...) -> bool
    def measure_planning_efficiency() -> Dict
    def analyze_adaptation() -> Dict
```

### TaskSuccessTracker

```python
class TaskSuccessTracker:
    def create_task(task_id: str, description: str) -> TaskRecord
    def record_attempt(task_id: str, attempt: TaskAttempt) -> None
    def get_success_metrics() -> Dict
    def generate_task_report() -> Dict
    def get_trending_improvement() -> Optional[float]
```

---

## 🔍 トラブルシューティング

### Q: スコアが期待より低い

**A**: 以下の手順で診断してください：

1. **次元別スコアを確認**
   ```python
   print(score.dimensions.to_dict())
   ```

2. **弱点を特定**
   ```python
   print(score.weaknesses)
   ```

3. **推奨事項を確認**
   ```python
   print(score.recommendations)
   ```

### Q: 評価に一貫性がない

**A**: 以下を確認してください：

1. 入力メトリクスが正確か
2. テスト環境が一定か
3. 評価期間が十分か（最低5回以上の評価）

### Q: 計画測定が不正確

**A**:
1. 各ステップのトークン推定を改善
2. ステップの依存関係を明確に定義
3. 実行ログを詳細に記録

---

## 📖 リソース

### ソースコードファイル

- [autonomy_scorer.py](../src/agent/autonomy/autonomy_scorer.py) - スコアリングエンジン
- [decision_analyzer.py](../src/agent/autonomy/decision_analyzer.py) - 意思決定分析
- [planning_measurer.py](../src/agent/autonomy/planning_measurer.py) - 計画測定
- [task_tracker.py](../src/agent/autonomy/task_tracker.py) - タスク追跡
- [examples.py](../src/agent/autonomy/examples.py) - 使用例

### テストファイル

```bash
# すべてのテストを実行
pytest tests/agent/test_autonomy/ -v

# 特定のモジュールをテスト
pytest tests/agent/test_autonomy/test_autonomy_scorer.py -v
pytest tests/agent/test_autonomy/test_decision_analyzer.py -v
```

---

## 📝 バージョン履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2025-04-21 | 初期リリース |

---

## 📧 サポート

フレームワークに関する質問や問題がある場合は、以下をご参照ください：

- 📖 [ドキュメント](./src/agent/autonomy/__init__.py)
- 💻 [ソースコード](../src/agent/autonomy/)
- 🧪 [テストスイート](../tests/agent/test_autonomy/)
- 📝 [使用例](../src/agent/autonomy/examples.py)

---

**作成**: GitHub Copilot Assistant  
**最終更新**: 2025-04-21  
**プロジェクト**: Agent Autonomy Evaluation Framework
