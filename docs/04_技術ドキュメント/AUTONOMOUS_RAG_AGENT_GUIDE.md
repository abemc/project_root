# 自律型 RAG Agent - バックアップ・リストア統合ガイド

## 概要

自律型RAGエージェント（`autonomous_rag_agent.py`）は、バックアップ・リストア機能を統合した自動実行型のRAGシステムです。Streamlitダッシュボードに依存せず、CLIコマンドで全ての操作が可能です。

## 主な機能

### 1. 質問処理（RAG クエリ）
ドキュメントを参照して自動的に質問に回答します。

```bash
python autonomous_rag_agent.py --query "ドキュメント管理について" -v
```

安全確認付きで実行する場合:

```bash
python autonomous_rag_agent.py --query "ドキュメント管理について" --human-in-the-loop --strict-ethics
```

**出力例:**
```
🔍 RAG Query を実行...

📤 質問処理開始
   質問: ドキュメント管理について
   モデル: GPT-4o
   検索方式: ハイブリッド
   検索結果: 5個のドキュメント

💬 応答:
[質問に対する回答]

📚 参照ドキュメント (5 個):
  1. ドキュメント.md (root)
  2. ...
```

### 2. 設定管理

#### 現在の設定を表示
```bash
python autonomous_rag_agent.py --show-config
```

**表示内容:**
- LLM モデル
- 検索パラメータ
- 生成パラメータ
- バックアップ先設定

#### 設定をエクスポート
```bash
python autonomous_rag_agent.py --export-config my_config.json
```

#### 設定をインポート
```bash
python autonomous_rag_agent.py --import-config my_config.json
```

### 3. バックアップ・リストア

#### バックアップを作成
```bash
python autonomous_rag_agent.py --backup
```

**実行結果:**
```
💾 バックアップを実行...
✅ 設定をバックアップしました
   ファイル: /home/abemc/project_root/config/rag_backups/rag_config_backup_20260420_160619.json
```

#### バックアップ一覧を表示
```bash
python autonomous_rag_agent.py --list-backups
```

**実行結果:**
```
📋 バックアップ履歴 (5 個)
----------------------------------------------------------------------
1. rag_config_backup_20260420_160619.json
   📅 2026-04-20 16:06:19
   📊 0.12 MB

2. rag_config_backup_20260420_155821.json
   📅 2026-04-20 15:58:21
   📊 0.12 MB
...
```

#### 最新のバックアップからリストア
```bash
python autonomous_rag_agent.py --restore
```

#### 特定のバックアップからリストア
```bash
python autonomous_rag_agent.py --restore rag_config_backup_20260420_160619.json
```

## ファイル構成

```
project_root/
├── autonomous_rag_agent.py          ← メインエージェント
├── rag_agent_config.py              ← 設定管理モジュール
├── docs_manager.py                  ← ドキュメント管理
├── config/
│   ├── rag_agent_config.json        ← 現在の設定
│   └── rag_backups/                 ← バックアップ保存先
│       ├── rag_config_backup_*.json
│       └── ...
└── docs/                            ← ドキュメント格納先
```

## 設定ファイルの構造

```json
{
  "version": "1.0",
  "created": "2026-04-20T16:00:00",
  "llm_model": "GPT-4o",
  "search_method": "ハイブリッド",
  "top_k": 5,
  "confidence_threshold": 0.7,
  "temperature": 0.7,
  "max_tokens": 2000,
  "document_categories": ["root", "reports", "guides"],
  "enable_cache": true,
  "cache_ttl": 3600,
  "system_prompt": "あなたは優秀なドキュメント分析専門家です...",
  "enable_source_attribution": true,
  "enable_follow_up_questions": true,
  "language": "ja",
  "backup_location": "/mnt/d/backups"
}
```

## 使用例

### 例1: 日常的な質問処理
```bash
# 質問を実行
python autonomous_rag_agent.py --query "セキュリティについて" -v
```

### 例2: 定期バックアップ
```bash
# 毎日のバックアップを cron で実行
0 2 * * * cd /home/abemc/project_root && python autonomous_rag_agent.py --backup
```

### 例3: 設定のプリセット管理
```bash
# プロダクション用設定をエクスポート
python autonomous_rag_agent.py --export-config configs/production.json

# ステージング用設定をインポート
python autonomous_rag_agent.py --import-config configs/staging.json
```

### 例4: 障害時のリストア
```bash
# 最新のバックアップから復帰
python autonomous_rag_agent.py --restore

# または特定のバージョンから復帰
python autonomous_rag_agent.py --restore rag_config_backup_20260420_140000.json
```

## コマンドリファレンス

| コマンド | 説明 |
|---------|------|
| `--query TEXT` | 質問を実行 |
| `--backup` | 設定をバックアップ |
| `--restore [FILE]` | 設定をリストア（FILE省略で最新） |
| `--list-backups` | バックアップ一覧を表示 |
| `--show-config` | 現在の設定を表示 |
| `--export-config FILE` | 設定をエクスポート |
| `--import-config FILE` | 設定をインポート |
| `--human-in-the-loop` | 回答表示前に確認プロンプトを挟む |
| `--strict-ethics` | 倫理監査が warning/fail（または高リスク）の場合に回答をブロック |
| `--show-ethics-report` | 倫理監査サマリーを表示 |
| `--ethics-report-hours N` | 倫理レポート集計期間（時間） |
| `--save-response-log` | 応答を `logs/agent_responses.jsonl` に保存 |
| `-v, --verbose` | 詳細出力モード |

## 戻り値（終了コード）

- `0`: 成功
- `1`: エラー発生
- `2`: Human-in-the-loop でユーザーが表示を中止

## 詳細オプション

### 詳細出力モード
```bash
python autonomous_rag_agent.py --query "質問" -v
```

質問処理の詳細ログを表示します：
- 質問文
- 使用モデル
- 検索方式
- 検索結果数

### 倫理監査レポート
```bash
python autonomous_rag_agent.py --show-ethics-report --ethics-report-hours 24
```

### 応答ログ保存
```bash
python autonomous_rag_agent.py --query "質問" --save-response-log
```

## 安全制御（CLI と実行経路共通）

現在の実装では、以下の安全制御が有効です。

- 倫理監査（バイアス/透明性）
- confidence と倫理スコアの複合リスク判定
- strict モード時の高リスク回答ブロック

`src/rag/agent.py` 側は環境変数で有効化できます。

```bash
export RAG_STRICT_ETHICS=true
export RAG_SAVE_RESPONSE_LOG=true

# JSONLログのローテーション設定（任意）
export RAG_LOG_MAX_BYTES=5242880     # 5MB
export RAG_LOG_BACKUP_COUNT=3        # 保持世代数
```

## ログ仕様

主要ログファイル:

- `logs/history.jsonl`: 実行トレース履歴
- `logs/ethics_audit.jsonl`: 倫理監査結果
- `logs/agent_responses.jsonl`: 応答・リスク判定ログ

ローテーション仕様:
- 閾値 (`RAG_LOG_MAX_BYTES`) 超過時に `.1`, `.2` ... へ世代ローテーション
- 保持世代数は `RAG_LOG_BACKUP_COUNT` で制御

確認コマンド:

```bash
tail -20 logs/ethics_audit.jsonl
tail -20 logs/agent_responses.jsonl
```

## バックアップ戦略

### 自動バックアップ
```bash
# Linux crontab で定期バックアップ
# 毎日午前2時にバックアップを実行
0 2 * * * python /home/abemc/project_root/autonomous_rag_agent.py --backup
```

### バージョン管理
バックアップファイルは自動的にタイムスタンプ付けされます：
```
rag_config_backup_20260420_160619.json
                    ├─ 2026年
                    ├─ 04月
                    ├─ 20日
                    ├─ 16時
                    ├─ 06分
                    └─ 19秒
```

### バックアップの保存先
デフォルト: `/home/abemc/project_root/config/rag_backups/`

カスタム設定は `rag_agent_config.json` の `backup_location` で変更可能

## トラブルシューティング

### バックアップが見つからない
```bash
# バックアップ一覧を確認
python autonomous_rag_agent.py --list-backups
```

### 設定ファイルが破損した
```bash
# 最新のバックアップからリストア
python autonomous_rag_agent.py --restore

# または自動リセット
python autonomous_rag_agent.py --import-config configs/default.json
```

### 質問処理が遅い
```bash
# 設定で検索結果数を調整
python autonomous_rag_agent.py --show-config
```

`top_k` を減らすと処理が高速化されます。

## 統合例

### 外部スクリプトから呼び出し
```python
from autonomous_rag_agent import AutonomousRAGAgent

# RAG Agent を初期化
agent = AutonomousRAGAgent()

# 質問を実行
response = agent.query("ドキュメント管理について")

# 応答を処理
print(response['answer'])
print(f"参照ドキュメント: {response['source_count']} 個")

# バックアップを作成
agent.backup_config()
```

### Webhook イベント連携
```bash
#!/bin/bash
# webhook_handler.sh

EVENT=$1

if [ "$EVENT" = "config_changed" ]; then
  # 設定変更時にバックアップを作成
  python autonomous_rag_agent.py --backup
fi

if [ "$EVENT" = "disaster_recovery" ]; then
  # 災害復旧時に最新バックアップからリストア
  python autonomous_rag_agent.py --restore
fi
```

## 注意事項

1. **バックアップ保存先**: 定期的にバックアップの保存先をチェックしてください
2. **ディスク容量**: バックアップは定期的に古いものを削除してください
3. **権限**: 設定ファイルには機密情報が含まれる可能性があるため、適切な権限管理を行ってください
4. **LLM統合**: 現在は応答がダミー実装です。実際のLLM（GPT-4o など）と統合する際には、APIキーの管理に注意してください

## 次のステップ

1. **LLM統合**: `_generate_answer()` メソッドに実際のLLM統合を実装
2. **キャッシング**: 応答結果のキャッシング機構を追加
3. **ログ記録**: 質問・応答のログを保存
4. **メトリクス収集**: 応答の品質メトリクスを計測

---

**作成日**: 2026-04-20  
**バージョン**: 1.0
