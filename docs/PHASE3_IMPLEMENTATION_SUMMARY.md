# Phase 3 実装サマリー: 安全性・倫理

**実装完了日**: 2026-05-17  
**対象範囲**: 安全性・説明責任・倫理的価値の管理  
**行数合計**: 約1,450行（4ファイル）

---

## 📊 実装統計

| モジュール | ファイル | 行数 | 主要クラス数 | メソッド数 |
|-----------|---------|------|-----------|----------|
| Permission Manager | src/safety/permission_manager.py | 500 | 3 | 12 |
| Decision Explainer | src/explainability/decision_explainer.py | 380 | 2 | 10 |
| Value Conflict Resolver | src/ethics/value_conflict_resolver.py | 420 | 2 | 12 |
| Sandbox Executor | src/sandbox/sandbox_executor.py | 450 | 2 | 11 |
| **合計** | **4ファイル** | **~1,750** | **9** | **45** |

---

## 🔐 PermissionManager: アクセス制御

### 概要
ツール実行権を 2 次元マトリックス（ToolAccessLevel × AutonomyLevel）で管理。
4 × 4 = 16 の権限パターンと 7 つのデフォルトポリシーを実装。

### キークラス

#### `ToolAccessLevel` (Enum)
- `READ_ONLY`: 読み取り専用 (web_search など)
- `WRITE_LIMITED`: 制限付き書き込み (file_create など)
- `WRITE_FULL`: 完全な書き込み (file_modify など)
- `CRITICAL`: 重要システム操作 (system_config_change など)

#### `AutonomyLevel` (Enum)
- `SUPERVISED`: 完全な監視下 (全て承認必須)
- `SEMI_AUTONOMOUS`: 半自律 (低リスク操作は承認不要)
- `AUTONOMOUS`: 自律 (承認不要な操作が多い)
- `RESTRICTED`: 制限 (セキュリティベルトダウン時)

#### `PermissionManager` (クラス)
主要メソッド:
- `can_execute()`: ツール実行可否を判定
- `requires_approval()`: 承認が必要か判定
- `get_allowed_tools()`: 実行可能ツール一覧を取得
- `get_approval_required_tools()`: 承認必須ツール一覧を取得
- `record_execution()`: 実行を記録してレート制限をチェック
- `get_permission_summary()`: 権限の現在状況をレポート

### デフォルトポリシー
7 つのツールポリシーが事前定義:
- `web_search`: READ_ONLY
- `database_query`: READ_ONLY
- `file_create`: WRITE_LIMITED
- `file_modify`: WRITE_LIMITED
- `file_delete`: CRITICAL
- `system_config_change`: CRITICAL
- `authentication_change`: CRITICAL

### レート制限
時間当たりの実行回数上限:
- file_delete: 5/時間
- system_config_change: 2/時間
- その他: 50/時間

---

## 💡 DecisionExplainer: 意思決定の透明化

### 概要
AI エージェントが「なぜこのツールを選んだか」「なぜこのパラメータか」を
自然言語で説明し、透明性と信頼性を確保。

### キークラス

#### `ExplanationType` (Enum)
- `TOOL_SELECTION`: ツール選択理由
- `PARAMETER_CHOICE`: パラメータ選択理由
- `STRATEGY_RATIONALE`: 戦略の根拠
- `REJECTION_REASON`: 却下理由
- `CONFIDENCE_SCORE`: 信頼度説明

#### `ExplanationItem` (Dataclass)
実行可能な説明の詳細データ:
- `explanation_type`: 説明種別
- `content`: 説明文
- `reasoning_chain`: 推論ステップ（リスト）
- `evidence`: 根拠データ
- `confidence`: 説明の確信度 (0-1)
- `alternatives`: 他の選択肢
- `timestamp`: タイムスタンプ

#### `DecisionExplainer` (クラス)
主要メソッド:
- `explain_tool_selection()`: ツール選択を説明（信頼度に応じて3段階）
- `explain_parameter_selection()`: パラメータ選択を説明
- `explain_strategy()`: 戦略選択を説明
- `explain_rejection()`: ツール却下理由を説明
- `explain_confidence()`: 信頼度スコアを説明
- `get_explanation()`: 説明を取得
- `get_all_explanations()`: 全説明を取得
- `get_explanations_by_type()`: 種別別に説明を取得
- `export_explanation_report()`: レポートをエクスポート

### テンプレート
5 つの説明テンプレートを事前定義:
1. `tool_selection_high_conf`: 高確信度（成功率データ付き）
2. `tool_selection_medium_conf`: 中確信度（代替案付き）
3. `tool_selection_low_conf`: 低確信度（推奨される監視レベル）
4. `parameter_selection`: パラメータ選択（範囲と成功率付き）
5. `strategy_rationale`: 戦略選択（利益・リスク分析付き）

---

## ⚖️ ValueConflictResolver: 倫理的価値管理

### 概要
プライバシー vs 有用性、安全性 vs 効率性など
複数の価値が衝突する場合にユーザーポリシーに基づいて解決。

### キークラス

#### `Value` (Enum)
8 つの基本価値:
- `PRIVACY`: プライバシー保護
- `UTILITY`: 利用可能性・有用性
- `SAFETY`: 安全性
- `EFFICIENCY`: 効率性
- `TRANSPARENCY`: 透明性
- `AUTONOMY`: 自律性
- `FAIRNESS`: 公平性
- `ACCOUNTABILITY`: 説明責任

#### `ValuePriority` (Dataclass)
価値の優先度設定:
- `value`: 価値タイプ
- `weight`: 重要度 (0-1)
- `threshold`: 最小満足度 (0-1)
- `override_allowed`: オーバーライド許可

#### `ConflictScenario` (Dataclass)
衝突シナリオ:
- `scenario_id`: シナリオID
- `conflicting_values`: 衝突する価値リスト
- `action_proposed`: 提案アクション
- `impact_analysis`: 各価値への影響 (-1〜1)
- `user_policy`: ユーザーポリシー（スナップショット）
- `resolved_decision`: 解決決定
- `resolution_timestamp`: タイムスタンプ

#### `ValueConflictResolver` (クラス)
主要メソッド:
- `resolve_conflict()`: 価値衝突を解決（スコア付き）
  - 戻り値: (決定, 総合スコア, 詳細情報)
- `set_user_policy()`: ユーザーポリシーを設定
- `suggest_alternative_action()`: 代替案を提案
- `explain_resolution()`: 解決過程を説明
- `get_conflict_statistics()`: 衝突統計を取得

### デフォルトポリシー
SAFETY を最高優先度 (1.0, threshold=0.9)、
AUTONOMY を最低優先度 (0.5, threshold=0.3) に設定。
全てのポリシーは override_allowed パラメータで柔軟性を提供。

### 解決戦略
1. **全価値満足**: APPROVE
2. **単一違反・許可可**: APPROVE_WITH_MITIGATION
3. **単一違反・重要**: REJECT
4. **複数違反**: REJECT

---

## 🔒 SandboxExecutor: 隔離環境実行

### 概要
未検証のツール・アクション実行を隔離環境（Docker/subprocess）で行い、
結果を検証してから本番環境に適用。

### キークラス

#### `SandboxType` (Enum)
- `DOCKER_CONTAINER`: Docker コンテナ（最高隔離）
- `VIRTUAL_ENV`: Python 仮想環境
- `SUBPROCESS`: サブプロセス（最小隔離）
- `KUBERNETES_POD`: Kubernetes Pod

#### `ExecutionStatus` (Enum)
- `PENDING`: 待機中
- `RUNNING`: 実行中
- `SUCCESS`: 成功
- `FAILED`: 失敗
- `TIMEOUT`: タイムアウト
- `SECURITY_BLOCKED`: セキュリティ理由で遮断

#### `ExecutionPolicy` (Dataclass)
実行ポリシー:
- `timeout_seconds`: タイムアウト (デフォルト 30 秒)
- `max_memory_mb`: メモリ上限 (デフォルト 512 MB)
- `max_cpu_percent`: CPU 上限 (デフォルト 50%)
- `allow_network`: ネットワークアクセス (デフォルト False)
- `allow_filesystem_write`: ファイル書き込み (デフォルト False)
- `max_file_size_mb`: 最大ファイルサイズ (デフォルト 10 MB)
- `allowed_system_calls`: 許可システムコール

#### `SandboxResult` (Dataclass)
実行結果:
- `execution_id`: 実行ID
- `status`: 実行ステータス
- `output`: 実行出力
- `error_output`: エラー出力
- `return_code`: リターンコード
- `execution_time`: 実行時間（秒）
- `resource_usage`: リソース使用率
- `validation_passed`: 検証合格
- `safety_score`: 安全スコア (0-1)

#### `SandboxExecutor` (クラス)
主要メソッド:
- `execute_in_sandbox()`: サンドボックスで実行
  - セキュリティチェック → 実行 → 検証
- `_security_check()`: セキュリティチェック
  - 危険なコマンド、ネットワーク、FS 書き込みの禁止
- `_validate_result()`: 実行結果を検証
  - 6 種類の検証チェック + カスタムルール
- `apply_to_production()`: 本番環境に適用
- `compare_results()`: 2 つの実行結果を比較
- `get_execution_report()`: レポートを取得
- `get_sandbox_statistics()`: 統計を取得

### セキュリティチェック
実行時に以下をブロック:
- 危険なコマンド: rm, mkfs, dd, chmod, reboot, kill など
- ネットワークコマンド: curl, wget, ssh, ftp など（policy で許可なし）
- ファイル書き込みコマンド: filesystem_write policy なし時

### 検証ルール
6 つの自動検証チェック:
1. ステータス OK (SUCCESS)
2. リターンコード OK (0)
3. タイムアウト OK (タイムアウトなし)
4. セキュリティ OK (ブロックなし)
5. 出力サイズ OK (ファイルサイズ制限内)
6. エラー出力 OK (成功時のみ)

---

## 📦 パッケージ構成

```
src/
├── safety/
│   ├── __init__.py
│   └── permission_manager.py      # PermissionManager
├── explainability/
│   ├── __init__.py
│   └── decision_explainer.py       # DecisionExplainer
├── ethics/
│   ├── __init__.py
│   └── value_conflict_resolver.py  # ValueConflictResolver
└── sandbox/
    ├── __init__.py
    └── sandbox_executor.py         # SandboxExecutor
```

---

## 🧪 テスト

[tests/test_phase3_integration.py](../tests/test_phase3_integration.py)

### テストカバレッジ
- **TestPermissionManagerIntegration**: 基本的なツール権、承認、レート制限
- **TestDecisionExplainerIntegration**: 説明生成（高/中/低信頼度）、レポート
- **TestValueConflictResolverIntegration**: 衝突解決、代替案提案、統計
- **TestSandboxExecutorIntegration**: 安全/危険なコマンド、検証、統計
- **TestPhase3FullIntegration**: 全体統合ワークフロー、監査証跡

テスト実行:
```bash
pytest tests/test_phase3_integration.py -v
```

---

## 🔗 Phase 1〜3 統合フロー

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
[Phase 3] 安全性・倫理 ← NEW
  ├─ Permission: アクセス制御をチェック
  ├─ Explanation: 決定を説明
  ├─ ValueConflict: 倫理的衝突を解決
  └─ Sandbox: 隔離環境で実行・検証
  ↓
出力: 検証済み結果をユーザーに返却
```

---

## 📈 次のステップ (Phase 4)

**Phase 4: 実行環境（8-12週目）**

1. **Tool Executor**: 実際の OS コマンド実行
   - Permission Manager を実装
   - Sandbox Executor を統合
   - エラーハンドリング

2. **Event Loop**: 非同期実行管理
   - ReAct Loop の非同期化
   - 複数ツールの並行実行
   - キャンセレーション

3. **Fallback Chain**: エラーからの復帰
   - Error Learning と統合
   - 代替ツール選択
   - 自動リトライ

4. **Production Deployment**: 本番環境化
   - 監視・ロギング
   - パフォーマンス最適化
   - セキュリティ監査

---

## 📝 実装ノート

- **テンプレート駆動**: 説明とポリシーをテンプレートで管理し、
  保守性・拡張性を確保
- **2 次元マトリックス**: アクセス制御を 2 軸で表現し、
  複雑な権限ルールをシンプルに
- **検証チェーン**: セキュリティ → 実行 → 検証の 3 段階で、
  安全性と実行可能性のバランスを取る
- **価値ベース**: 倫理的決定を数値化し、
  トレードオフを定量的に管理

---

## 📚 参考資料

- AUTONOMOUS_AI_ASSESSMENT.md: 全体ロードマップ
- PHASE2_IMPLEMENTATION_SUMMARY.md: 前フェーズの記録
- docs/DYNAMIC_TASK_MANAGER.md: タスク管理の詳細
- docs/RAG_Episodic_AutoRepair_Plan.md: メモリ・学習の詳細
