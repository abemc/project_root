# プロジェクト解析機能：要件定義と実装計画

作成日: 2026-05-05
作成者: GitHub Copilot（支援）

## 目的
ワークスペース内のプロジェクト構造・重要ファイル・依存関係・設計意図などを自動で解析し、開発者に要約・可視化・検索可能なメタ情報を提供する機能を実装する。

## 目標（成果物）
- ワークスペース走査モジュール（対象ファイル抽出、メタデータ収集）
- LLM呼び出しラッパー（プロンプトテンプレート、チャンク分割戦略）
- 解析結果を出力するJSONスキーマ
- CLI と簡易 Streamlit UI（オンデマンド解析、結果表示）
- テストと使用例（サンプル出力）

## スコープ（含む・除外）
- 含む:
  - ソースコード（.py, .js, .ts, .java 等）とREADME、設計ドキュメント（.md）
  - requirements.txt / pyproject.toml / package.json 等の依存情報
  - 主要バイナリや大容量ファイルはメタ情報のみ収集
- 除外:
  - バイナリ解析（ELF等の逆アセンブル）
  - クラウド認証情報やシークレットの自動送信（検出したら警告のみ）

## 要件
### 機能要件
1. ワークスペース走査
   - 再帰的に走査し、ファイルタイプ、サイズ、最終更新日時、言語推定を収集
   - `.gitignore` と同等の除外ルールを適用可能
   - ファイルごとに先頭/末尾のスニペット（N行）を保持
2. メタデータ抽出
   - モジュール名、関数・クラスの数、依存パッケージ一覧（静的解析）
   - READMEやドキュメントからプロジェクト概要を抽出
3. 解析/要約
   - ファイル群の役割要約（例: "API層: app.py, routes/..."）
   - アーキテクチャ概要、主要コンポーネント、データフロー推定
   - 未実装TODOやFIXMEの抽出
4. LLMラッパー
   - プロンプトテンプレートを分離して管理
   - 大きなファイルはチャンク化し、逐次要約→統合（map-reduce）方式
   - プロバイダ切替（OpenAI API / ローカルLlama系）の抽象化
5. 出力
   - JSONで保存（スキーマを定義）
   - 人間向け要約（Markdown）出力オプション
6. インターフェース
   - CLI: `analyze-project --path . --output out.json` のような使用感
   - Streamlit: ワークスペース選択、解析実行、結果のツリー表示

### 非機能要件
- セキュリティ: シークレットは送信しない。検出したらログ/警告のみ。
- 設定: `rag_agent_config.py` とは別に `project_analyzer.yaml` などで構成
- 拡張性: 将来、静的解析プラグインや可視化プラグインを追加可能
- 実行時間: 中規模リポジトリ（数千ファイル）でも段階的に解析できること

## データ収集の詳細仕様
- 対象拡張子（初期）: .py, .md, .txt, .json, .yaml, .yml, .toml, .ini, .js, .ts, .java
- サイズ閾値: ファイル > 1MB はフル送信せずヘッダ＋サンプルのみ
- 文字エンコーディング: UTF-8を前提。変換できないファイルはスキップしてログに記録
- 除外パターン: node_modules, __pycache__, .venv, .git, build, dist 等

## 出力スキーマ（概要）
- project_summary: { title, short_description, top_languages, loc_estimate }
- files: [ { path, size, lang, snippet, hashes, roles } ]
- dependencies: { python: [], node: [], other: [] }
- components: [ { name, role, files: [], summary } ]
- issues: [ { type: TODO|FIXME|SECRET, location, excerpt } ]
- llm_logs: { prompt_hash, tokens_used, provider, timestamp }

（詳細スキーマは実装時に OpenAPI/JSON Schema で落とす）

## LLM統合設計
- 抽象インターフェース: `LLMClient` に `summarize(text, context)` と `batch_summarize(chunks, strategy)` を用意
- 環境設定:
  - `ANALYZER_LLM_PROVIDER`（openai|local|mock）
  - `OPENAI_API_KEY`（必要時）
  - `ANALYZER_MAX_TOKENS`, `ANALYZER_CHUNK_SIZE` 等
- プロンプト設計:
  - ファイル要約プロンプト（目的・期待出力の例）
  - 統合プロンプト（コンポーネント要約、アーキテクチャ推定）
- チャンク戦略:
  - map: 各チャンクを要約
  - reduce: 要約同士を統合して最終要約
  - メタ情報（ファイル名・行番号）をプロンプトに含める

## 実装アーキテクチャ（モジュール構成案）
- analyzer/
  - scanner.py        # ファイル走査、除外ルール
  - extractor.py      # メタデータ抽出（静的解析）
  - llm_client.py     # 抽象LLMクライアント + OpenAI/local実装
  - summarizer.py     # チャンク化、map-reduce集約
  - cli.py            # CLIエントリポイント
  - ui_streamlit.py   # Streamlit UI
  - schema.py         # 出力スキーマ定義
  - tests/            # 単体テスト

## テスト計画
- ユニットテスト: scanner, extractor の主要機能
- 統合テスト: 小さなサンプルリポジトリで解析→期待スキーマと比較
- LLMモック: 実APIコールを行わないモック実装で高速テスト

## スケジュール（粗）
- Week 0: 要件確定（完了）
- Week 1: `scanner.py`, `schema.py` の実装、ユニットテスト
- Week 2: `extractor.py`, `llm_client.py`（モック実装含む）
- Week 3: `summarizer.py`（map-reduce）とCLI
- Week 4: Streamlit UI + 統合テスト + ドキュメント

## リスクと対策
- LLMコスト大: 重要度の低いファイルは要約オプションでスキップ可能にする
- シークレット漏洩: シークレット検出ルールを実装し、検出時は送信しない
- 大規模リポジトリでの時間: インクリメンタル解析とキャッシュを導入

## セキュリティ/プライバシー
- デフォルトでローカルモード（LLM未指定）を推奨
- 外部API利用時は明示的設定を必須にする
- 解析ログは機密情報削除ポリシーに従う

## 次の作業（短期）
1. `analyzer/scanner.py` のプロトタイプ作成（走査・除外ルール）
2. `docs/project_analyzer_plan.md` をレビューして承認
3. `analyzer/schema.py` で JSON Schema を定義

---

作成元: 要件定義ミーティング（自動生成）
