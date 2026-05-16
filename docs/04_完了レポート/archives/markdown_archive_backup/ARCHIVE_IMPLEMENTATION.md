# 🗂️ メトリクスアーカイブ機能 - 実装ドキュメント

## 📌 概要

メトリクスデータが無限に増え続ける問題を解決するために、**アーカイブ機能**を実装しました。古いデータを自動的に別ファイルに移動し、ディスク容量を効率的に管理します。

## 🎯 機能

### 1. **自動アーカイブ**
```python
# メトリクスを記録する際に自動実行
tracker = MetricTracker()
tracker.record_snapshot(...)  # 内部で自動アーカイブ判定
```

### 2. **保持期間管理**
- **retention_days**: 90日（デフォルト）以上前のデータを自動アーカイブ
- 最新90日分のデータはメインファイルに保持

### 3. **ファイルサイズ管理**
- **max_file_size_mb**: 100MB（デフォルト）を超えたら分割
- 7日ごとのファイル分割で最適化

### 4. **自動クリーンアップ**
- 保持期間の2倍以上前のアーカイブを自動削除
- ディスク容量を効率的に利用

## 📂 ファイル構造

```
logs/metrics/
├── metrics_history.jsonl           # メインファイル（最新90日分）
└── archive/                         # アーカイブディレクトリ
    ├── metrics_archive_20260410.jsonl
    ├── metrics_archive_20260409.jsonl
    └── metrics_archive_20260408.jsonl
```

## ⚙️ 設定（config.py）

```python
@dataclass
class MetricsConfig:
    # アーカイブ設定
    archive_enabled: bool = True           # 有効化
    retention_days: int = 90               # 保持期間（日）
    archive_dir: str = "logs/metrics/archive"  # アーカイブディレクトリ
    max_file_size_mb: int = 100            # ファイルサイズ上限
    auto_cleanup: bool = True              # 自動クリーンアップ
```

## 🔧 API リファレンス

### MetricTracker クラス

```python
# アーカイブ情報取得
info = tracker.get_archive_info()
# 返り値:
# {
#     "main_file_size_mb": 0.05,
#     "total_archived_size_mb": 15.20,
#     "archive_count": 12,
#     "retention_days": 90,
#     "archive_enabled": True,
#     "archives": [
#         {
#             "filename": "metrics_archive_20260410.jsonl",
#             "size_mb": 1.50,
#             "created": "2026-04-10T10:00:00"
#         },
#         ...
#     ]
# }

# 保持期間ベースのアーカイブ
tracker._archive_by_retention()

# ファイルサイズベースのアーカイブ
tracker._archive_by_size()

# 古いアーカイブの削除
tracker._cleanup_old_archives()

# アーカイブから復元
tracker.restore_from_archive("metrics_archive_20260410.jsonl")
```

## 🛠️ 管理ツール（archive_util.py）

### 使用方法

```bash
cd /home/abemc/project_root

# アーカイブ情報を表示
PYTHONPATH=. python tools/archive_util.py info

# 最近のスナップショットを表示
PYTHONPATH=. python tools/archive_util.py snapshots [N]

# ヘルプを表示
PYTHONPATH=. python tools/archive_util.py help
```

### コマンド一覧

| コマンド | 説明 | 例 |
|---------|------|-----|
| `info` | アーカイブ情報を表示 | `python archive_util.py info` |
| `snapshots [N]` | 最近のNスナップショット表示 | `python archive_util.py snapshots 20` |
| `cleanup` | 古いアーカイブを削除 | `python archive_util.py cleanup` |
| `restore <name>` | アーカイブから復元 | `python archive_util.py restore metrics_archive_20260410.jsonl` |
| `export [file]` | アーカイブサマリーをエクスポート | `python archive_util.py export summary.json` |
| `help` | ヘルプを表示 | `python archive_util.py help` |

## 📊 動作フロー

```
スナップショット記録
    ↓
ファイルサイズチェック
    ├─ 100MB超過 → ファイルサイズベースのアーカイブ
    └─ OK ↓
保持期間チェック
    ├─ 90日超過 → 保持期間ベースのアーカイブ
    └─ OK ↓
古いアーカイブクリーンアップ
    ↓
アーカイブ完成
```

## 💾 ストレージ効率

### 例: 1年間のメトリクス

| 指標 | 値 |
|------|-----|
| 記録間隔 | 10回/日 |
| 1日のレコード数 | 10個 |
| 1ファイルサイズ | 500 bytes/レコード |
| 1年分のサイズ | 10 × 365 × 0.5KB ≈ 1.8MB |
| **アーカイブ後（90日保持）** | 最新90日：0.45MB + アーカイブ：1.35MB = **1.8MB** |
| **メインファイルサイズ** | **0.45MB** |

### メリット

✅ メインファイルが常に0.5MB以下（軽い）
✅ 過去1年分のデータを保持（90日は即座に、古いのはアーカイブ）
✅ 自動管理でディスク容量の心配なし
✅ 必要に応じてアーカイブから復元

## 🚨 トラブルシューティング

### 問題: アーカイブが作成されない

**原因**: retention_days が0の場合

```python
# config.py でチェック
config = get_config("metrics")
print(config.retention_days)  # 90 であることを確認
```

### 問題: アーカイブから復元がうまくいかない

```bash
# 利用可能なアーカイブを確認
PYTHONPATH=. python tools/archive_util.py info

# 正確なファイル名で復元
PYTHONPATH=. python tools/archive_util.py restore metrics_archive_20260410.jsonl
```

### 問題: ディスク容量がまだ増え続ける

**原因**: FeedbackManager や ContinuousTrainer も同様のデータ蓄積

```
対象ファイル:
- logs/feedback/feedback_history.jsonl
- logs/prompts/templates.jsonl
- checkpoints/micro_finetune/checkpoints.jsonl
```

→ 各マネージャーにも同様のアーカイブ機能を実装予定

## 📈 監視コマンド

```bash
# リアルタイムでファイルサイズを監視
watch -n 60 'du -sh logs/metrics* checkpoints/micro_finetune*'

# 月ごとのアーカイブ数を確認
ls -la logs/metrics/archive/ | grep "20260"

# アーカイブの統計情報
du -sh logs/metrics/archive/* | sort -h
```

## 🔐 バックアップ推奨

```bash
# アーカイブのバックアップを作成
tar -czf metrics_backup_$(date +%Y%m%d).tar.gz logs/metrics/archive/

# 外部ドライブに保存（例）
cp metrics_backup_$(date +%Y%m%d).tar.gz /mnt/backup/
```

## 📚 実装詳細

### MetricTracker の内部処理

1. **_auto_archive()** - アーカイブ判定と実行
2. **_archive_by_retention()** - 保持期間ベースのアーカイブ
3. **_archive_by_size()** - ファイルサイズベースのアーカイブ
4. **_rewrite_metrics_file()** - ファイルを再作成
5. **_cleanup_old_archives()** - 古いアーカイブを削除

### 主要な変更点

- `metric_tracker.py`: アーカイブ機能追加（10メソッド）
- `config.py`: MetricsConfig にアーカイブ設定追加
- `archive_util.py`: 新規作成（管理ツール）
- `tests/test_self_improvement.py`: テスト追加

## ✅ テスト結果

```
🧪 アーカイブ機能 テスト
✅ テストデータ記録: 30個のスナップショット
✅ アーカイブ情報取得: メインファイル 0.01MB
✅ 保持期間ベースのアーカイブ: 動作確認
✅ ファイルサイズベースのアーカイブ: 動作確認
✅ 古いアーカイブのクリーンアップ: 動作確認
✅ アーカイブから復元: 動作確認

📊 合計: 6/6 テスト成功 🎉
```

---

**実装完了日**: 2026年4月10日
**ステータス**: ✅ 本番対応可能
**互換性**: 既存コードと完全に互換
