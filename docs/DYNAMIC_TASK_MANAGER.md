# 動的タスクマネージャ設計案

目的
- 既存の `AgentEngine` / `TaskPlanner` を拡張し、実行中に優先度・依存関係・リソースを再評価してタスク順序を動的に再編成できるコンポーネント設計を示す。

要件（高レベル）
- 実行時の優先度再評価（優先度スコアの再計算）
- 依存関係に基づく安全な再編成
- ユーザー承認やポリシー（require_approval）を尊重
- 障害時のロールバック / 再試行戦略
- メトリクス収集（成功率、平均遅延、介入率）

アーキテクチャ概要
- `DynamicTaskManager`（DTM）: 実行ループのオーケストレータ
  - 主要責務: 受け取った `ExecutionPlan` を監視・スケジュールし、外部イベントやメトリクスに応じて `execution_order` を再計算する
  - 組み込みサブコンポーネント:
    - `PriorityEvaluator`: タスク毎のスコア算出（成功確率、コスト、緊急度、ユーザーインプット）
    - `DependencyResolver`: 依存の検証と安全な順序変更の判定
    - `Replanner`: 再計画ポリシー（閾値越えで再計画）
    - `Monitor`: 実行中メトリクス収集 + 異常検知

実行フロー（簡易）
1. `AgentEngine.execute_goal()` が `planner.decompose_task()` で `ExecutionPlan` を生成
2. `DynamicTaskManager` が `ExecutionPlan` を受け取り、最初の `execution_order` を決定して実行を開始
3. 各サブタスク実行後に `Monitor` が結果/メトリクスを返す
4. `PriorityEvaluator` が各サブタスクのスコアを更新。総スコア差が `REPLAN_THRESHOLD` を超えたら `Replanner` を起動
5. `Replanner` は `DependencyResolver` を使って安全に順序を再編成し、必要ならユーザー承認を要求

動的再優先化の指標候補
- 期待成功確率（historical success × current confidence）
- 予想実行コスト（秒／リソース要件）
- 緊急度（ユーザー優先度、期限）
- 依存度（再実行コストの高低）

障害・リトライポリシー
- 各 `SubTask` は `max_retries` を持つ
- 再試行は指数バックオフ（ベース=2秒, max=60秒）
- 重要タスク失敗時のサーキットブレーカー（一定回数失敗でそのタスクを一時停止）

インタフェース（擬似）
```
class DynamicTaskManager:
    def __init__(self, planner, executor, monitor): ...
    def execute_plan(self, plan: ExecutionPlan, user_approvals: Dict[str,bool]=None) -> Dict:
        """Returns execution summary and metrics"""

    def evaluate_priorities(self, plan: ExecutionPlan) -> Dict[str,float]: ...
    def replan_if_needed(self, plan: ExecutionPlan) -> ExecutionPlan: ...
```

小規模実装ステップ（提案）
1. `src/agent_architecture/dynamic_task_manager.py` を追加し、最小実装（評価器は簡易スコア: success_rate - cost）を作る
2. `scripts/task_demo.py` を拡張して、`DynamicTaskManager.execute_plan()` を呼ぶオプションを追加
3. ユニットテスト `tests/test_dynamic_task_manager.py` を追加（再優先化、依存保持、リトライ動作）
4. ドキュメントと例を `docs/` に追加

次のステップ（私がすぐやれること）
- `src/agent_architecture/dynamic_task_manager.py` のスケルトン実装を作成します（最小で動くもの）。進めて良いですか？
