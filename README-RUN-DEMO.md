# デモ実行手順（簡易ガイド）

目的
- ローカルで `scripts/task_demo.py` を使って AgentEngine / DynamicTaskManager の挙動を確認するための最小手順。

前提
- Python 3.10 がインストールされていること。
- リポジトリルートで実行すること（`/home/abemc/project_root`）。

推奨環境変数
- `PYTHONPATH=.` を使うと `src` を確実にインポートできます。

基本コマンド

1) フォールバック（最小デモ）

```bash
python3 scripts/task_demo.py "検索して要約を作成する"
```a

2) プロジェクト `src` を読み込む（推奨）

```bash
PYTHONPATH=. python3 scripts/task_demo.py "検索して要約を作成する"
```

3) `DynamicTaskManager` を使う（可能なら）

```bash
PYTHONPATH=. python3 scripts/task_demo.py "検索して要約を作成する" --use-dtm
```

テスト実行（DTM のユニットテスト）

```bash
PYTHONPATH=. python -m pytest -q tests/test_dynamic_task_manager.py
```

トラブルシュート
- ImportError が出る場合は必ず `PYTHONPATH=.` を付けてください。
- 実行時に LLM 等の外部依存が必要な場合は、まず `requirements.txt` を確認して仮想環境にインストールしてください。

補足
- デモは最小限の挙動確認用です。本番想定の実行では `AgentEngine` の設定や `RAG` 用のコーパス・モデル準備が必要です。
