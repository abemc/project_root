# 📦 プロジェクトバックアップ・リストアガイド

## 概要

プロジェクトが肥大化するにつれ、重要なデータの安全な管理が必須になります。このバックアップシステムは、プロジェクト全体を効率的にバックアップ・リストアできるように設計されています。

## 🎯 機能

## 🎯 機能

### バックアップ対象（9カテゴリ）

| 対象 | パス | 説明 | 含有量 |
|-----|------|------|--------|
| **system_config** | .env, .github, pyproject.toml, requirements.txt, Dockerfile, docker-compose.yml, .streamlit | システム設定・CI/CD・インフラ | 小 |
| **source_code** | src/ | ソースコード全体（rag, embeddings, train等 | 中 |
| **scripts** | build_knowledge.py, manage_kb.py, main.py等 | ユーティリティスクリプト | 小 |
| **data_input** | raw_pdfs, data, notebooks | 入力データ・ノートブック | 可変 |
| **embeddings** | embeddings, rag_corpus | 埋め込みベクトル・RAGコーパス | **⚠️ 大 |
| **models** | models, fine_tuned_model, checkpoints | モデルファイル・チェックポイント | **⚠️ 大 |
| **knowledge_base** | corpus | 知識ベースコーパス | **⚠️ 極大 |
| **documentation** | *.md, docs | ドキュメント | 小 |
| **logs** | logs/ | 実行ログ・履歴 | 中 |

### 機能一覧

- ✅ **選択的バックアップ**: 特定のターゲットのみバックアップ
- ✅ **圧縮サポート**: tar.gz自動圧縮で容量削減
- ✅ **メタデータ管理**: JSON形式のマニフェスト
- ✅ **リストア機能**: 簡単な復元
- ✅ **自動クリーンアップ**: 古いバックアップを自動削除
- ✅ **除外パターン**: pyc、__pycache__など自動除外

## 🚀 使い方

### ⭐ 【推奨】外部ドライブにバックアップを保存

#### 方法1: コマンドラインで直接指定（最も簡単）

```bash
# Linux / WSL
python tools/backup_cli.py --external-drive /mnt/external_drive create --compress

# Windows (WSL経由で D: ドライブ)
python tools/backup_cli.py --drive D: create --compress

# macOS (外部ドライブ /Volumes/External)
python tools/backup_cli.py --external-drive /Volumes/External create --compress
```

#### 方法2: 環境変数で設定（毎回指定不要）

1. `.env.example` をコピー
   ```bash
   cp .env.example .env
   ```

2. `.env` ファイルを編集
   ```bash
   # Linux / WSL
   BACKUP_ROOT=/mnt/external_drive/backups
   
   # Windows (WSL 経由)
   BACKUP_ROOT=/mnt/d/backups
   
   # macOS
   BACKUP_ROOT=/Volumes/External/project_backups
   ```

3. バックアップコマンドを実行（ドライブ指定不要）
   ```bash
   python tools/backup_cli.py create --compress
   ```

### 方法1: Streamlit UI

app.pyを実行したら、サイドバーの「💾 プロジェクトバックアップ・リストア」セクションを使用します。

```
1. バックアップ対象を選択（デフォルト：system_config, source_code, documentation）
   - ⚠️ embeddings, models, knowledge_base は大容量のため個別確認を推奨
2. オプション設定（圧縮など）
3. [✨ バックアップを作成] をクリック
```

### 方法2: CLIツール

#### 基本的な使用方法

```bash
# バックアップを作成（推奨設定：軽量版・自動圧縮）
python tools/backup_cli.py create --targets "system_config,source_code,documentation" --notes "Daily backup $(date +%Y-%m-%d)"
```

# 圧縮を無効化（大きなストレージの場合）
python tools/backup_cli.py create --targets "system_config,source_code,documentation" --no-compress

# 中容量版
python tools/backup_cli.py create --targets "system_config,source_code,scripts,data_input,documentation,logs" --notes "Weekly backup"

# フル版（大容量注意）
python tools/backup_cli.py create --targets "system_config,source_code,scripts,data_input,embeddings,models,knowledge_base,documentation,logs" --notes "Monthly full backup"

# バックアップ一覧
python tools/backup_cli.py list

# バックアップ情報
python tools/backup_cli.py info backup_id

# リストア
python tools/backup_cli.py restore backup_id

# 削除
python tools/backup_cli.py delete backup_id

# クリーンアップ（30日以上前＆5個以上のみ削除）
python tools/backup_cli.py cleanup --keep-days 30 --keep-count 5
```

#### カスタム保存先の指定

```bash
# 【新】外部ドライブを指定（--external-drive）- Linux/Mac/WSL
python tools/backup_cli.py --external-drive /mnt/external_drive create --targets "system_config,source_code,documentation"

# 【新】短いオプション利用（--drive）- Windows WSL推奨
python tools/backup_cli.py --drive D: create --targets "system_config,source_code,documentation"

# 【従来】--backup-root でも可能
python tools/backup_cli.py --backup-root "/mnt/external_drive/backups" create --targets "system_config,source_code,documentation"

# Windowsの場合
python tools/backup_cli.py --external-drive "D:\\backups" create --targets "system_config,source_code,documentation"

# 外部ストレージで保存先クオリティのあるとき確認
python tools/backup_cli.py --external-drive /mnt/external_drive list

# 外部ストレージを指定してリストア
python tools/backup_cli.py --external-drive /mnt/external_drive restore backup_id
```

## 📊 バックアップマニフェスト

各バックアップには `manifest.json` が含まれ、以下の情報を記録します：

```json
{
  "backup_id": "20260410_143022",
  "timestamp": "2026-04-10T14:30:22.123456",
  "version": "0.1.0",
  "total_size": 524288000,
  "items": [
    {
      "source_path": "prompt.txt",
      "relative_path": "prompt.txt",
      "file_count": 1,
      "total_size": 5240,
      "item_type": "file"
    },
    {
      "source_path": "logs/feedback",
      "relative_path": "logs/feedback",
      "file_count": 125,
      "total_size": 2048000,
      "item_type": "folder"
    }
  ],
  "config": {},
  "notes": "Spring release backup"
}
```

## � 復旧方法（リストア）

### 方法1: Streamlit UIでリストア

サイドバーの「💾 プロジェクトバックアップ・リストア」セクション内で：

1. **バックアップを選択**
   - 「バックアップを選択」ドロップダウンから復旧したいバックアップを選択
   - ファイル数、サイズ、タイムスタンプが表示されます

2. **詳細情報を確認**
   - 「📋 詳細情報」を展開
   - マニフェストをチェックして、復旧内容を確認

3. **リストア実行**
   - 「🔄 リストア」ボタンをクリック
   - 復旧完了メッセージが表示されます
   - アプリケーションを再読み込みしてください

### 方法2: CLIでリストア

#### 基本的なリストア

```bash
# デフォルト保存先からリストア
python tools/backup_cli.py restore backup_id

# 例：20260411_000737 というバックアップをリストア
python tools/backup_cli.py restore 20260411_000737
```

#### 別ディレクトリへのリストア

```bash
# テストディレクトリへ復旧
python tools/backup_cli.py restore backup_id --restore-root "/tmp/test_restore"

# 別フォルダへ復旧
python tools/backup_cli.py restore backup_id --restore-root "/home/user/project_backup"

# カスタム保存先＋別復旧先
python tools/backup_cli.py --backup-root "/mnt/external/backups" restore backup_id --restore-root "/tmp/verify"
```

### 方法3: プログラムからリストア

```python
from src.backup import ProjectBackupManager

# 初期化
manager = ProjectBackupManager(
    project_root="/path/to/project",
    backup_root="/path/to/backups"
)

# リストア実行
success = manager.restore_backup(
    backup_id="20260411_000737",
    restore_root="/path/to/restore_destination",  # 省略時はプロジェクトルート
    verify=True  # マニフェスト検証有効
)

if success:
    print("✅ リストア完了")
else:
    print("❌ リストア失敗")
```

### リストア時の確認ポイント

**復旧前に以下をチェック：**

```bash
# 1. バックアップ一覧で対象を確認
python tools/backup_cli.py list

# 2. バックアップ内容を確認
python tools/backup_cli.py info backup_id

# 3. ディスク容量を確認（復旧に十分か）
df -h /path/to/restore_destination

# 4. 書き込み権限を確認
touch /path/to/restore_destination/test.txt && rm /path/to/restore_destination/test.txt
```

### リストアシナリオ別ガイド

#### ✅ 全ファイル復旧（通常のリストア）
```bash
python tools/backup_cli.py restore backup_id
# → プロジェクトルートに全ファイルを復旧
```

#### ✅ マージ復旧（新しいファイルのみ保持）
```bash
# リストア前にバックアップをディレクトリに一時抽出
tar -xzf backups/backup_id.tar.gz -C /tmp/restore_tmp/

# 特定のファイルだけを手動でコピー
cp -i /tmp/restore_tmp/src/* ./src/
# -i オプション：上書き確認
```

#### ✅ 別ディレクトリへのテストリストア
```python
from src.backup import ProjectBackupManager

manager = ProjectBackupManager("/path/to/project")

# テスト用ディレクトリに復旧
manager.restore_backup(
    backup_id="backup_id",
    restore_root="/tmp/test_restore"
)

# 復旧内容を確認してから本番復旧
```

#### ✅ 特定のターゲットのみ復旧
```bash
# マニフェストを確認
python tools/backup_cli.py info backup_id | python -m json.tool

# tar.gzから特定パスのみ抽出
tar -tzf backups/backup_id.tar.gz | grep "source_code/"
tar -xzf backups/backup_id.tar.gz "source_code/" -C ./

# または手動でディレクトリに抽出してからコピー
tar -xzf backups/backup_id.tar.gz -C /tmp/
cp -r /tmp/source_code ./
```

## �💡 ベストプラクティス
### 推奨ドライブ設定戦略

#### 1. 環境変数で外部ドライブを設定（最も推奨）

```bash
# .env ファイルに設定
echo "BACKUP_ROOT=/mnt/external_drive/backups" >> .env

# 以後、毎回ドライブ指定不要
python tools/backup_cli.py create --compress
```

**メリット**:
- ✅ コマンドが簡潔
- ✅ 設定は .env で管理
- ✅ 複数のスクリプトで統一可能
- ✅ 環境ごとに設定可能

#### 2. コマンドラインで毎回指定

```bash
python tools/backup_cli.py --external-drive /mnt/external create --compress
```

**メリット**:
- ✅ .env を修正しない
- ✅ 一時的な変更に最適
- ✅ スクリプト内で動的に変更可能

#### 3. 複数のドライブを切り替え

```bash
# 日次: 高速ローカルドライブ
python tools/backup_cli.py --external-drive /mnt/fast_ssd create --compress

# 月次: 安全な外付けドライブ
python tools/backup_cli.py --external-drive /mnt/external_usb create --compress
```
### 推奨バックアップ戦略

#### 日次バックアップ（軽量版）
```bash
# 重要な設定・ソース・ドキュメント のみ（自動圧縮）
python tools/backup_cli.py create \
  --targets "system_config,source_code,documentation" \
  --notes "Daily incremental backup $(date +%Y-%m-%d)"
```

#### 週次バックアップ（中容量版）
```bash
# + ログ・スクリプト・入力データ（自動圧縮）
python tools/backup_cli.py create \
  --targets "system_config,source_code,scripts,data_input,documentation,logs" \
  --notes "Weekly comprehensive backup"
```

#### 月次バックアップ（フル版）
```bash
# すべて含める（高容量注意・自動圧縮）
python tools/backup_cli.py create \
  --targets "system_config,source_code,scripts,data_input,embeddings,models,knowledge_base,documentation,logs" \
  --notes "Monthly full backup - $(date +%Y-%m)"
```

#### クリティカル保存ポイント
```bash
# 重要な変更の直前・直後（自動圧縮）
python tools/backup_cli.py create \
  --targets "source_code,models,fine_tuned_model" \
  --notes "Before major training run"
```

### ストレージ管理

```bash
# 30日以上前のバックアップを削除（ただし常に5個以上保持）
python tools/backup_cli.py cleanup --keep-days 30 --keep-count 5

# 手動で古いバックアップ確認・削除
python tools/backup_cli.py list
python tools/backup_cli.py delete backup_id_to_remove
```

### バックアップサイズ推定

| ターゲット | 推定サイズ | 圧縮後 |
|----------|----------|--------|
| system_config | 1-2 MB | 0.5 MB |
| source_code | 5-20 MB | 2-5 MB |
| scripts | 1-5 MB | 0.5-2 MB |
| data_input | 100MB-10GB | 50-5000 MB |
| embeddings | 1-100 GB | 0.5-50 GB |
| models | 2-50 GB | 1-25 GB |
| knowledge_base | 5-500 GB | 2-200 GB |
| documentation | 1-10 MB | 0.5-5 MB |
| logs | 50-500 MB | 5-50 MB |

**推奨**: 月次フル含まず日次バックアップで月50-200MB、月次も追加で数GB程度確保

### 検証手順

```bash
# バックアップの詳細情報をチェック
python tools/backup_cli.py info backup_id

# マニフェストを見やすく表示
python tools/backup_cli.py info backup_id | python -m json.tool
```

## 🔧 プログラムからの使用

### Python API

```python
from src.backup import ProjectBackupManager

# 初期化
manager = ProjectBackupManager(
    project_root="/path/to/project",
    backup_root="/path/to/backups",
    compress=True
)

# バックアップ作成
backup_path, manifest = manager.create_backup(
    targets=["system_config", "source_code", "documentation"],
    backup_name="my_backup",
    compression=True,
    notes="Important project backup"
)

# バックアップ一覧
backups = manager.list_backups()
for backup in backups:
    print(f"{backup['backup_id']}: {backup['total_size_mb']} MB")

# リストア
manager.restore_backup("my_backup")

# 削除
manager.delete_backup("my_backup")

# クリーンアップ
manager.cleanup_old_backups(keep_days=30, keep_count=5)

# サイズ確認
size = manager.get_backup_size("my_backup")
print(f"Size: {size / (1024**2):.2f} MB")
```

### マニフェスト操作

```python
from src.backup.manifest import BackupManifest, BackupItem

# ロード
manifest = BackupManifest.load("backups/backup_id/manifest.json")

# 情報取得
summary = manifest.get_summary()
print(summary)
# {
#     'backup_id': '...',
#     'timestamp': '...',
#     'item_count': 7,
#     'total_size_mb': 245.3,
#     'total_files': 1250
# }

# アイテム確認
for item in manifest.items:
    print(f"{item.relative_path}: {item.file_count} files")
```

## 📁 ディレクトリ構造

```
project_root/
└── backups/                    # バックアップ保存先
    ├── 20260410_143022/        # ディレクトリ形式
    │   ├── manifest.json
    │   ├── prompt.txt
    │   ├── logs/
    │   └── src/
    ├── 20260410_120000.tar.gz   # 圧縮形式
    └── ...
```

## ⚠️ 注意事項

### 大容量ファイル（バックアップに慎重）

- **knowledge_base（corpus）**: 数GB～数百GB ⚠️⚠️⚠️
- **embeddings（rag_corpus）**: 数GB～数十GB ⚠️⚠️
- **models（fine_tuned_model, checkpoints）**: 数GB～数十GB ⚠️⚠️
- **data_input（raw_pdfs）**: 可変（数100MB～数GB）
- HF キャッシュ（hf_cache）: 自動的に除外

### バックアップ実行時間

```
軽量版（system_config, source_code, documentation）:
  → 数秒～10秒

中容量版（+scripts, data_input, logs）:
  → 10秒～1分

大容量版（+embeddings, models）:
  → 1分～10分

フル版（+knowledge_base）:
  → 10分～1時間以上（ネットワーク・ディスク速度に依存）
```

### ディスク容量の目安

```
推奨保持数: 日次7個 + 週次4個 + 月次3個 = 14個

1バックアップのサイズ（圧縮後目安）:
  - 軽量版:        1-5 MB
  - 中容量版:      50-200 MB
  - 大容量版:      1-10 GB
  - フル版:        20-100+ GB

総バックアップ容量（月次フル除外時）:
  ≈ (7 × 100MB) + (4 × 500MB) = 2.7 GB
  
総容量（月次フル含む場合）:
  ≈ 2.7GB + (3 × 20GB) = 62.7GB以上
```

## 🐛 トラブルシューティング

### バックアップ作成が遅い/ディスク容量不足

```bash
# 軽量版を作成（自動圧縮）
python tools/backup_cli.py create \
  --targets "system_config,source_code,documentation"

# または大容量ターゲットを除外（圧縮を無効化する場合）
python tools/backup_cli.py create \
  --targets "system_config,source_code,scripts,data_input,documentation,logs" \
  --no-compress
```

### 特定のターゲットのみリストアしたい

```bash
# マニフェストで含まれているパスを確認
python tools/backup_cli.py info backup_id

# tar.gzから手動で抽出
tar -tzf backups/backup_id.tar.gz | grep "source_path/pattern"
tar -xzf backups/backup_id.tar.gz "source_code/" -C /tmp/

# 特定ファイルのみコピー
cp -r /tmp/source_code/* ./src/
```

### リストア失敗時のトラブルシューティング

```bash
# 1. バックアップID確認
python tools/backup_cli.py list

# 2. バックアップ整合性チェック
python tools/backup_cli.py info backup_id

# 3. ファイルシステム権限確認
ls -la backups/
chmod 755 backups/

# 4. ディスク容量確認
df -h

# 5. マニフェスト検証
tar -tzf backups/backup_id.tar.gz | head
tar -xzf backups/backup_id.tar.gz manifest.json -O | python -m json.tool
```

### リストア後にファイルが見つからない

```bash
# リストア先を確認
ls -la ./src/
ls -la ./logs/

# リストアログを確認（存在する場合）
grep -i restore logs/backup.log

# 復旧内容をマニフェストから確認
python tools/backup_cli.py info backup_id | python -m json.tool
```

### ファイルが上書きされてしまった（リストア後の復旧）

```bash
# 別バージョンのバックアップから復旧
python tools/backup_cli.py list  # 他のバックアップを探す

# テストディレクトリに一度復旧して確認
mkdir -p /tmp/test_restore
python tools/backup_cli.py restore other_backup_id  # restore_root を指定していないなら別env で

# または手動抽出で確認
tar -xzf backups/other_backup_id.tar.gz -C /tmp/other_restore/
diff -r /tmp/other_restore/src ./src/
```

### 圧縮ファイルが破損した

```bash
# 整合性チェック
tar -tzf backups/backup_id.tar.gz > /dev/null && echo "OK" || echo "破損"

# 部分抽出を試す
tar -xzf backups/backup_id.tar.gz -C /tmp/restore/ 2>&1 | head -20
```

### 外部ストレージにバックアップできない

```bash
# ストレージのマウント確認（Linux/Mac）
mount | grep backup  # または df -h で確認

# 書き込み権限を確認
touch /mnt/external_drive/test.txt && rm /mnt/external_drive/test.txt

# パーミッションを修正
chmod u+w /mnt/external_drive

# ネットワークストレージの場合
# Windows: ネットワークドライブとしてマウント
# Linux: sudo mount -t nfs server:/path /mnt/backup
```

### 保存先パスが見つからない

```bash
# 絶対パスを確認
ls -la /mnt/external_drive/

# 相対パスの場合はプロジェクトルートから確認
cd /home/abemc/project_root
ls -la ../../external_backup/
```

## 📈 ストレージプランニング

### 推奨バックアップ戦略

```
本番環境:
  - 日次バックアップ（config, システム）: 最新7個保持
  - 週次バックアップ（全体含む）: 最新4個保持
  - 月次バックアップ（アーカイブ）: 12個保持

開発環境:
  - 必要に応じて手動作成
  - 重要変更前後のみ
```

### ストレージ容量計算

```
バックアップ総容量 = 
  日次 × 7 × 1GB ＋
  週次 × 4 × 8GB ＋
  月次 × 12 × 15GB

例: 1 + 32 + 180 = 213GB（外部ストレージ推奨）
```

## 🔐 セキュリティ考慮事項

### バックアップの保護

```bash
# ファイルパーミッション設定（Linux/Mac）
chmod 700 backups/

# ディレクトリ暗号化（オプション）
# ツール例: VeraCrypt, BitLocker, FileVault2
```

### 敏感データの除外

必要に応じて `EXCLUDE_PATTERNS` にパターンを追加：

```python
# backup_manager.py
EXCLUDE_PATTERNS = [
    "*.pyc", "__pycache__", ".pytest_cache",
    ".git", ".venv", "node_modules",
    "*.log", ".DS_Store", "*.tmp",
    "hf_cache",
    "api_keys.json",  # 追加
    "secrets/*",      # 追加
]
```

## 📞 サポート

バックアップに関する問題は、以下をご確認ください：

1. ログファイル: `logs/backup.log`
2. マニフェスト: `backups/backup_id/manifest.json`
3. ディスク容量: `df -h`

---

**最終更新**: 2026年4月
**バージョン**: 1.0.0
