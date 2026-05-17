# Tool Runbook（ツール実行手順書）

目的
- プロジェクト内で利用される外部ツール／内部ツールの一覧、実行ルール、承認フロー、失敗時対応を一元化する。

1) ツール一覧（代表例）
- `search_doc`: ローカルコーパス検索。入力: `query`。出力: ドキュメントリスト。
- `search_web`: Web 検索（`search_web_tool` ラッパー）。入力: `query`。
- `answer`: 最終回答生成（LLM呼び出し）。入力: `prompt`。
- `rewrite_query`: クエリ書換え（LLM補助）。
- `read_file` / `write_file`: ファイルIO。`write_file` は `require_approval` 推奨。
- `run_shell`: シェル実行。危険を伴うため `require_approval=True` 推奨。

2) ツール定義テンプレート（例）
```
Tool(
  name="run_shell",
  tool_type=ToolType.ACTION,
  description="シェルコマンドを実行する（安全化済）",
  execute_fn=run_shell_safe,
  required_params=["command"],
  require_approval=True,
)
```

3) 承認フロー
- `require_approval=True` のツールは `AgentEngine` / `ToolExecutor` で `user_approval` をチェックする。
- 自動実行モード（`AutonomyLevel.AUTONOMOUS`）では承認をスキップするが、ログと監査を必須にする。

4) 安全対策（実行前チェック）
- `run_shell` などの危険なツールは `shlex` 分割 + whitelist コマンドのみ許可。
- `write_file` は書き込み先を検査し、プロジェクト外パスや機密ファイルを拒否。
- PII マスキング: `security_manager.mask_pii()` を通す。

5) 失敗時の標準対応
- 失敗分類: transient / permanent
  - transient: 再試行（指数バックオフ）
  - permanent: エラーログ化、代替プランへフォールバック
- 再試行ルール: `max_retries`（サブタスク単位）および `retry_manager` を利用。
- サーキットブレーカー: 同一ツールで短時間に複数失敗が発生したら一定期間停止。

6) ロギングと監査
- 各ツール呼び出しは `execution_time`, `status`, `tool_name`, `params`（マスク済）を `logs/tool_calls.jsonl` に出力。
- 倫理監査が有効な場合は `ethics_monitor.audit_response()` を呼び出し結果を保存する。

7) テストとモック
- 単体テストでは `execute_fn` をモック可能にする（例: `MockExecutor` を利用）。
- CI では `run_shell` 等の実行をスキップするフラグを用意。

8) 開発者向けチェックリスト
- 新しいツールを追加する場合:
  1. `Tool` 定義を `src/agent_architecture/` に追加
  2. 必要な `required_params` を定義
  3. `require_approval` の要否をレビュー
  4. 危険度に応じたユニットテストとモックを作成
  5. `docs/TOOL_RUNBOOK.md` にエントリを追加

9) 参照実装
- `src/rag/agent.py` 内の `_handle_run_shell`, `_handle_write_file` を参照。

---
このドキュメントは運用中に更新してください。重大な変更（新しい危険ツールの導入等）はチーム合意を得た上で追加します。
