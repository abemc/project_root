# タスク分解テンプレート

目的: ゴールを自己完結的に（可能な範囲で）分解し、実行計画に落とし込むための最小テンプレート。

1. ゴール（Main Goal）
   - 例: 「レポート用に関連文献を集め、要約を作成する」

2. 背景・コンテキスト
   - 前提条件、利用可能なデータ、時間制約、優先度

3. 成果物 (Deliverables)
   - 何を出力するか（ファイル名・形式・品質基準）

4. サブタスク (Subtasks)
   - 各サブタスクに以下を定義する:
     - `task_id` (例: task_1)
     - `description`（具体的な作業）
     - `required_tools`（例えば: web_search, pdf_parser, summarizer）
     - `dependencies`（先行タスク）
     - `estimated_time`（分単位）
     - `require_approval`（True/False）

5. 実行順序 (Execution Order)
   - 依存関係に基づく順序リスト

6. 失敗時の振る舞い（Retry / Rollback）
   - max_retries, backoff, 代替プラン

7. 監視・メトリクス
   - 成功基準、KPI（成功率、平均実行時間、介入回数）

8. エグザンプル（簡易）
   - Main Goal: 文献を検索し3件要約を作る
   - Subtasks:
     - task_1: クエリ最適化（tool: rewrite_query）
     - task_2: コーパス検索（tool: search_doc）
     - task_3: 要約作成（tool: summarizer）
   - Execution Order: [task_1, task_2, task_3]

---
補足: このテンプレートを `docs/` 以下に保存し、具体的なゴールごとにコピーして使ってください。
