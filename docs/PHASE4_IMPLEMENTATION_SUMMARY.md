# Phase 4 実装サマリー: 実行環境

**実装完了日**: 2026-05-18  
**対象範囲**: ツール実行、非同期イベントループ、エラー復帰  
**行数合計**: 約1,900行（3ファイル）

---

## 📊 実装統計

| モジュール | ファイル | 行数 | 主要クラス数 | メソッド数 |
|-----------|---------|------|-----------|----------|
| Tool Executor | src/execution/tool_executor.py | 680 | 4 | 18 |
| Event Loop | src/execution/event_loop.py | 700 | 4 | 20 |
| Fallback Chain | src/execution/fallback_chain.py | 520 | 2 | 12 |
| **合計** | **3ファイル** | **~1,900** | **10** | **50** |

---

## 🛠️ ToolExecutor: 実際のツール実行

### 概要
Permission Manager による権限チェック → Sandbox Executor で検証 →
本番環境での実行という一貫性のある実行パイプラインを提供。
4 段階の実行フェーズ（権限・検証・実行・結果検証）を実装。

### キークラス

#### `ToolType` (Enum)
- `SYSTEM_COMMAND`: OS コマンド (echo, ls など)
- `PYTHON_FUNCTION`: Python 関数実行
- `API_CALL`: 外部 API 呼び出し
- `DATABASE_QUERY`: DB クエリ実行
- `FILE_OPERATION`: ファイル操作
- `SHELL_SCRIPT`: シェルスクリプト実行

#### `ExecutionPhase` (Enum)
4 段階の実行フェーズ:
- `PERMISSION_CHECK`: 権限チェック
- `SANDBOX_VALIDATION`: サンドボックス検証
- `PRODUCTION_EXECUTION`: 本番実行
- `RESULT_VALIDATION`: 結果検証
- `COMPLETION`: 完了

#### `ToolDefinition` (Dataclass)
ツール定義:
- `name`: ツール名
- `tool_type`: ツール種別
- `description`: 説明
- `timeout_seconds`: タイムアウト時間
- `requires_approval`: 承認必須か
- `max_retries`: 最大リトライ回数
- `retry_delay_seconds`: リトライ間隔
- `custom_validator`: カスタム検証関数
- `environment_vars`: 環境変数
- `allowed_args`: 許可引数パターン

#### `ToolRegistry` (クラス)
ツール定義の管理:
- `register_tool()`: ツールを登録
- `get_tool()`: ツール定義を取得
- `get_all_tools()`: 全ツール取得

デフォルト登録ツール (6 個):
- web_search (READ_ONLY, 30s タイムアウト)
- file_create (WRITE_LIMITED, 10s, 承認必須)
- file_modify (WRITE_LIMITED, 10s, 承認必須)
- file_delete (CRITICAL, 5s, 承認必須, リトライなし)
- database_query (READ_ONLY, 60s タイムアウト)
- api_call (READ_ONLY, 30s タイムアウト)

#### `ExecutionResult` (Dataclass)
実行結果:
- `execution_id`: 実行ID
- `tool_name`: ツール名
- `status`: 実行状態
- `output`: 標準出力
- `error_output`: エラー出力
- `return_code`: リターンコード
- `execution_time`: 実行時間（秒）
- `phase_results`: 各フェーズの成否
- `safety_score`: 安全スコア (0-1)
- `retry_count`: リトライ回数

#### `ToolExecutor` (クラス)
主要メソッド:
- `execute_tool()`: ツールを実行
  - 4 段階のフェーズを順序実行
  - リトライロジック統合
  - 戻り値: ExecutionResult（詳細情報付き）
- `_phase_permission_check()`: 権限チェック
  - Permission Manager と統合
  - 承認コールバック処理
- `_phase_sandbox_validation()`: サンドボックス検証
  - Sandbox Executor と統合
  - 検証スコア確認
- `_phase_production_execution()`: 本番実行
  - 実際のコマンド実行
  - リトライロジック
  - 決定説明（Decision Explainer 統合）
- `_phase_result_validation()`: 結果検証
  - カスタムバリデータ実行
  - リターンコード確認
- `get_tool_executor_statistics()`: 統計取得

### 実行パイプライン

```
入力: tool_name, args, autonomy_level
  ↓
[Phase 1] PERMISSION_CHECK
  - Permission Manager で実行権確認
  - 承認が必要な場合はコールバック実行
  ↓
[Phase 2] SANDBOX_VALIDATION (オプション)
  - Sandbox Executor で安全性検証
  - 検証スコア確認
  ↓
[Phase 3] PRODUCTION_EXECUTION (リトライ付き)
  - 実際にツール実行
  - Decision Explainer で説明生成
  - エラー時はリトライ（max_retries 回）
  ↓
[Phase 4] RESULT_VALIDATION
  - カスタムバリデータ実行
  - リターンコード確認
  ↓
[Phase 5] COMPLETION
  - ExecutionResult を返却
```

---

## 🔄 EventLoop: 非同期実行管理

### 概要
複数のツール実行を並行管理し、イベント駆動型の実行パイプラインを提供。
タスクの優先度キューイング、スケジューリング、依存グラフ、イベント通知を実装。

### キークラス

#### `TaskPriority` (Enum)
- `CRITICAL`: 最高優先度 (1)
- `HIGH`: 高 (2)
- `NORMAL`: 通常 (3)
- `LOW`: 低 (4)
- `DEFERRED`: 最低優先度 (5)

#### `TaskStatus` (Enum)
- `PENDING`: 待機中
- `QUEUED`: キューに入った
- `RUNNING`: 実行中
- `PAUSED`: 一時停止
- `COMPLETED`: 完了
- `FAILED`: 失敗
- `CANCELLED`: キャンセル

#### `EventType` (Enum)
- `TASK_CREATED`: タスク作成
- `TASK_QUEUED`: キューに入った
- `TASK_STARTED`: 実行開始
- `TASK_PROGRESS`: 進行中
- `TASK_COMPLETED`: 完了
- `TASK_FAILED`: 失敗
- `TASK_CANCELLED`: キャンセル
- `LOOP_STARTED`: ループ開始
- `LOOP_STOPPED`: ループ停止
- `LOOP_ERROR`: ループエラー

#### `Task` (Dataclass)
実行タスク:
- `task_id`: タスク ID
- `tool_name`: ツール名
- `args`: ツール引数
- `priority`: 優先度
- `status`: ステータス
- `created_at`: 作成時刻
- `started_at`: 開始時刻
- `completed_at`: 完了時刻
- `result`: 実行結果
- `error`: エラーメッセージ
- `retries_remaining`: 残りリトライ回数
- `timeout_seconds`: タイムアウト時間
- `dependencies`: 依存タスク ID リスト
- `metadata`: メタデータ

#### `EventBus` (クラス)
イベント駆動管理:
- `subscribe()`: イベントハンドラを登録
- `unsubscribe()`: ハンドラを削除
- `publish()`: イベントを発行
- `get_event_history()`: イベント履歴を取得

#### `TaskGraph` (クラス)
タスク依存グラフ:
- `add_task()`: タスクを追加
- `add_dependency()`: 依存関係を追加
- `get_executable_tasks()`: 実行可能なタスクを取得（全依存完了済み）
- `has_circular_dependency()`: 循環依存をチェック

#### `EventLoop` (クラス)
主要メソッド:
- `schedule_task()`: タスクをスケジュール
  - 優先度キューにタスクを追加
  - 循環依存を検出してエラー
  - イベント発行
  - 戻り値: タスク ID
- `cancel_task()`: タスクをキャンセル
- `pause_task()`: タスクを一時停止
- `resume_task()`: 一時停止タスクを再開
- `start()`: イベントループを開始（別スレッド）
- `stop()`: イベントループを停止
- `get_task_status()`: タスク状態を取得
- `get_task_result()`: タスク結果を取得
- `get_running_tasks()`: 実行中タスク一覧
- `get_pending_tasks()`: 待機中タスク一覧
- `get_loop_statistics()`: 統計を取得

### 並行実行管理

```
schedule_task() → PriorityQueue
  ↓
[Event Loop (別スレッド)]
  ├─ get_executable_tasks() → 全依存完了済み
  ├─ max_concurrent_tasks までスロット確認
  ├─ _execute_task() → 別スレッド実行
  └─ イベント発行 (TASK_STARTED → COMPLETED/FAILED)
```

### 依存グラフの例

```
Task A (HIGH)
  ↓
Task B (NORMAL) [depends_on=[A]]
  ├─ Task C (NORMAL) [depends_on=[B]]
  └─ Task D (LOW) [depends_on=[B]]
```

---

## 🔁 FallbackChain: エラー復帰戦略

### 概要
Error Learning と統合して、類似エラーから復帰案を取得し、
段階的なフォールバック戦略を自動実行。
6 つの復帰戦略を優先度順に試行。

### キークラス

#### `FallbackStrategy` (Enum)
6 つの復帰戦略:
1. `RETRY_SAME`: 同じツール・パラメータで再試行（低信頼度）
2. `RETRY_MODIFIED`: 修正されたパラメータで再試行（中信頼度）
3. `ALTERNATIVE_TOOL`: 代替ツールに変更（中信頼度）
4. `DEGRADE_QUALITY`: 品質を落として簡易版実行（中信頼度）
5. `MANUAL_INTERVENTION`: ユーザー対応を要請（高信頼度）
6. `SKIP_TASK`: タスクをスキップ（低信頼度）

#### `FallbackOption` (Dataclass)
フォールバックオプション:
- `strategy`: 戦略種別
- `tool_name`: 代替ツール（ALTERNATIVE_TOOL 時）
- `modified_args`: 修正引数（RETRY_MODIFIED 時）
- `confidence`: このオプションの信頼度 (0-1)
- `reason`: フォールバック理由

#### `FallbackAttempt` (Dataclass)
フォールバック試行:
- `attempt_number`: 試行番号
- `strategy`: 使用戦略
- `original_error`: 元のエラーメッセージ
- `tool_name`: ツール名
- `args`: ツール引数
- `result`: 実行結果
- `success`: 成功したか
- `timestamp`: タイムスタンプ

#### `FallbackChain` (クラス)
主要メソッド:
- `get_fallback_options()`: フォールバックオプション一覧を取得
  - Error Learning から復帰案を検索
  - 標準フォールバック戦略を追加
  - 信頼度でソート
  - 戻り値: FallbackOption リスト（優先度順）
- `execute_fallback_chain()`: フォールバックチェーンを実行
  - 各オプションを信頼度順に試行
  - 成功時は即座に返却
  - 失敗時は次の戦略へ
  - 最大試行回数を制限
  - 戻り値: (成功, 結果, 試行履歴)
- `_suggest_modified_args()`: 修正パラメータを提案
  - タイムアウトエラー → パラメータを短縮
  - パーミッションエラー → より安全なパラメータ
  - メモリ制限 → より小さいサイズ
  - フォーマットエラー → 標準形式に修正
- `_suggest_alternative_tools()`: 代替ツール一覧を提案
  - ツール毎の代替候補を定義
- `_degrade_args()`: 品質低下版パラメータを生成
  - 最初のパラメータのみ使用
  - 計算量を削減
- `register_custom_strategy()`: カスタム戦略を登録
- `get_fallback_statistics()`: フォールバック統計を取得
- `get_fallback_report()`: エラー毎のレポートを生成

### 復帰戦略の選択フロー

```
エラー発生
  ↓
[Error Learning]
  ├─ 類似エラーを検索
  └─ 復帰案を取得 → FallbackOption に変換（最高信頼度）
  ↓
[標準戦略を追加]
  ├─ RETRY_SAME
  ├─ RETRY_MODIFIED (修正パラメータ提案)
  ├─ ALTERNATIVE_TOOL (代替ツール提案)
  ├─ DEGRADE_QUALITY
  ├─ MANUAL_INTERVENTION
  └─ SKIP_TASK
  ↓
[信頼度でソート]
  ↓
[順序で試行]
  ├─ attempt_1: オプション 1 を試行
  ├─ attempt_2: オプション 2 を試行
  └─ ...
  ↓
[成功時]
  → 即座に返却
  [全失敗時]
  → (False, None, attempts[]) を返却
```

---

## 📦 パッケージ構成

```
src/
├── execution/
│   ├── __init__.py
│   ├── tool_executor.py       # ToolExecutor, ToolRegistry
│   ├── event_loop.py           # EventLoop, Task, TaskGraph
│   └── fallback_chain.py       # FallbackChain, FallbackStrategy
```

---

## 🧪 テスト

[tests/test_phase4_integration.py](../tests/test_phase4_integration.py)

### テストカバレッジ
- **TestToolExecutorIntegration**: ツール実行、権限、フェーズ、統計
- **TestEventLoopIntegration**: タスク管理、優先度、依存グラフ、イベント
- **TestFallbackChainIntegration**: フォールバック選択、実行、統計
- **TestPhase4FullIntegration**: 全体統合、パイプライン

テスト実行:
```bash
pytest tests/test_phase4_integration.py -v
```

---

## 🔗 Phase 1-4 統合フロー（完全版）

```
入力: ユーザーリクエスト
  ↓
[Phase 1] ReAct Loop で計画・推論
  ├─ Plan: タスク分解
  ├─ Think: 選択肢を思考
  ├─ Act: ツール実行前準備
  └─ Reflect: 履歴を記録
  ↓
[Phase 2] 記憶・学習
  ├─ Memory: 過去のエピソードを検索
  ├─ Feedback: ユーザー修正を学習
  ├─ Error: 同様エラーから回復案を取得
  └─ Pattern: 成功パターンを抽出
  ↓
[Phase 3] 安全性・倫理
  ├─ Permission: アクセス制御をチェック
  ├─ Explanation: 決定を説明
  ├─ ValueConflict: 倫理的衝突を解決
  └─ Sandbox: 隔離環境で実行・検証
  ↓
[Phase 4] 実行環境 ← NEW
  ├─ ToolExecutor:
  │   ├─ [1] Permission Check
  │   ├─ [2] Sandbox Validation
  │   ├─ [3] Production Execution (+ リトライ)
  │   ├─ [4] Result Validation
  │   └─ [5] Completion
  │
  ├─ EventLoop:
  │   ├─ Task Scheduling (優先度キュー)
  │   ├─ Dependency Graph
  │   ├─ Concurrent Execution (max_concurrent)
  │   └─ Event Bus (イベント駆動)
  │
  └─ FallbackChain:
      ├─ Error Analysis
      ├─ Strategy Selection (6 戦略)
      ├─ Automatic Recovery
      └─ Error Learning 統合
  ↓
出力: 検証済み結果をユーザーに返却
```

---

## 📈 実装の特徴

### 1. **パイプライン設計**
   - 4 段階の明確なフェーズ（権限 → 検証 → 実行 → 検証）
   - 各フェーズの成否を詳細に記録
   - 段階的な安全性確保

### 2. **非同期実行管理**
   - 優先度キューによるタスク管理
   - 依存グラフによる順序制御
   - イベント駆動型の通知
   - 最大同時実行数の制御

### 3. **自動エラー復帰**
   - Error Learning と統合
   - 6 つの段階的な復帰戦略
   - 信頼度に基づいた選択
   - 最大リトライ回数の制限

### 4. **統合性**
   - Phase 3 (Permission, Explanation, Ethics, Sandbox) と完全統合
   - Phase 2 (Error Learning) と統合
   - 全モジュール間の情報フロー

---

## 📝 実装ノート

- **段階的実行**: 各フェーズの成否を個別に追跡することで、どこで失敗したかを正確に把握可能
- **優先度キュー**: 緊急度に基づいたタスク実行順序を自動管理
- **依存グラフ**: タスク間の依存関係を明示的に表現し、循環依存を検出
- **イベント駆動**: 各タスクの状態変化をイベントで通知することで、リアルタイム追跡が可能
- **信頼度ベース**: フォールバック戦略を信頼度で順序付けることで、最適な復帰経路を自動選択

---

## 🚀 次のステップ

本 Phase 4 で 4 柱モデルの実装は完了。

**残作業**:
1. 全テストの実行と検証
2. ドキュメント統合（AUTONOMOUS_AI_ASSESSMENT.md の更新）
3. 本番環境化（監視・ロギング・パフォーマンス最適化）
4. セキュリティ監査

---

## 📚 参考資料

- AUTONOMOUS_AI_ASSESSMENT.md: 全体ロードマップ
- PHASE3_IMPLEMENTATION_SUMMARY.md: Phase 3 実装記録
- PHASE2_IMPLEMENTATION_SUMMARY.md: Phase 2 実装記録
