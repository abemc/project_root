# RAGAgentConfig - API リファレンス・実装ガイド

## 目次

1. [クイックスタート](#クイックスタート)
2. [API リファレンス](#apiリファレンス)
3. [実装パターン](#実装パターン)
4. [テスト戦略](#テスト戦略)
5. [トラブルシューティング](#トラブルシューティング)
6. [ベストプラクティス](#ベストプラクティス)

---

## クイックスタート

### インストール

```python
# プロジェクトのルートディレクトリに rag_agent_config.py が存在することを確認

from rag_agent_config import RAGAgentConfig

# インスタンス作成
config = RAGAgentConfig()
```

### 最小限の使用例

```python
# 設定を読み込む
settings = config.load_config()

# 設定を変更して保存
settings['temperature'] = 0.8
config.save_config(settings)

# バックアップを作成
backup_path = config.backup_config()
print(f"Backup created: {backup_path}")
```

---

## API リファレンス

### クラス: `RAGAgentConfig`

#### コンストラクタ

```python
def __init__(self, config_dir: str = "/home/abemc/project_root/config")
```

**パラメータ:**
- `config_dir` (str): 設定ディレクトリのパス

**戻り値:** なし

**例:**
```python
# デフォルトディレクトリで初期化
config = RAGAgentConfig()

# カスタムディレクトリで初期化
config = RAGAgentConfig(config_dir="/custom/path/config")
```

**初期化時の動作:**
- 指定されたディレクトリが存在しない場合は作成
- バックアップディレクトリ(`rag_backups`)も作成

---

### メソッド: `load_config()`

```python
def load_config(self) -> Dict
```

**説明:** 設定ファイルを読み込む

**パラメータ:** なし

**戻り値:** 設定辞書 (`Dict`)

**例:**
```python
config_dict = config.load_config()
print(config_dict['llm_model'])  # 出力: GPT-4o
```

**詳細:**
- ファイルが存在する場合は読み込む
- ファイルが存在しない場合はデフォルト設定を返す
- JSON 形式で UTF-8 エンコーディング

---

### メソッド: `get_default_config()`

```python
def get_default_config(self) -> Dict
```

**説明:** デフォルト設定を返す

**パラメータ:** なし

**戻り値:** デフォルト設定辞書 (`Dict`)

**例:**
```python
default_config = config.get_default_config()
print(default_config['top_k'])  # 出力: 5
```

**デフォルト設定の内容:**

| キー | デフォルト値 |
|------|-------------|
| `version` | `"1.0"` |
| `created` | 現在の日時（ISO形式） |
| `llm_model` | `"GPT-4o"` |
| `search_method` | `"ハイブリッド"` |
| `top_k` | `5` |
| `confidence_threshold` | `0.7` |
| `document_categories` | `["root", "reports", "guides"]` |
| `enable_cache` | `True` |
| `cache_ttl` | `3600` |
| `max_tokens` | `2000` |
| `temperature` | `0.7` |
| `system_prompt` | （詳細なプロンプト文字列） |
| `enable_source_attribution` | `True` |
| `enable_follow_up_questions` | `True` |
| `language` | `"ja"` |
| `backup_location` | `"/mnt/d/backups"` |

---

### メソッド: `save_config(config)`

```python
def save_config(self, config: Dict) -> bool
```

**説明:** 設定をファイルに保存

**パラメータ:**
- `config` (Dict): 保存する設定辞書

**戻り値:** `True`（成功）、`False`（失敗）

**例:**
```python
config_dict = config.load_config()
config_dict['temperature'] = 0.9
success = config.save_config(config_dict)

if success:
    print("✅ 設定を保存しました")
else:
    print("❌ 保存に失敗しました")
```

**動作:**
- `last_modified` フィールドを自動的に追加
- JSON 形式（インデント2）で保存
- UTF-8 エンコーディング

---

### メソッド: `backup_config()`

```python
def backup_config(self) -> Optional[str]
```

**説明:** 現在の設定をバックアップ

**パラメータ:** なし

**戻り値:** バックアップファイルのパス（文字列）、失敗時は `None`

**例:**
```python
backup_path = config.backup_config()
if backup_path:
    print(f"✅ バックアップを作成しました: {backup_path}")
else:
    print("❌ バックアップの作成に失敗しました")
```

**バックアップファイル名形式:**
```
rag_config_backup_YYYYMMDD_HHMMSS.json
```

**例:**
```
rag_config_backup_20260401_120530.json
```

---

### メソッド: `restore_config(backup_file=None)`

```python
def restore_config(self, backup_file: Optional[str] = None) -> bool
```

**説明:** バックアップから設定を復元

**パラメータ:**
- `backup_file` (Optional[str]): 復元するバックアップファイルのパス。`None` の場合は最新のバックアップを使用

**戻り値:** `True`（成功）、`False`（失敗）

**例:**
```python
# 最新のバックアップから復元
success = config.restore_config()

# 特定のバックアップから復元
backup_file = "/home/abemc/project_root/config/rag_backups/rag_config_backup_20260401_120530.json"
success = config.restore_config(backup_file=backup_file)

if success:
    print("✅ 復元が完了しました")
else:
    print("❌ 復元に失敗しました")
```

---

### メソッド: `get_backups_list()`

```python
def get_backups_list(self) -> list
```

**説明:** バックアップファイルの一覧を取得

**パラメータ:** なし

**戻り値:** バックアップ情報の辞書リスト

**戻り値の形式:**
```python
[
    {
        'name': 'rag_config_backup_20260401_120530.json',
        'path': '/home/abemc/project_root/config/rag_backups/rag_config_backup_20260401_120530.json',
        'size': 1234,  # バイト
        'modified': '2026-04-01 12:05:30'
    },
    ...
]
```

**例:**
```python
backups = config.get_backups_list()
for backup in backups:
    print(f"{backup['name']} - {backup['modified']} ({backup['size']} bytes)")
```

---

### メソッド: `export_config(export_path)`

```python
def export_config(self, export_path: str) -> Optional[str]
```

**説明:** 設定を指定したフォルダにエクスポート

**パラメータ:**
- `export_path` (str): エクスポート先フォルダーパス

**戻り値:** エクスポートファイルのパス（文字列）、失敗時は `None`

**例:**
```python
export_path = config.export_config("/home/abemc/exports")
if export_path:
    print(f"✅ エクスポートが完了しました: {export_path}")
else:
    print("❌ エクスポートに失敗しました")
```

**例外:**
- `PermissionError`: 書き込み権限がない場合
- `OSError`: ファイルシステムエラーの場合

**書き込み権限チェック:**
```python
try:
    export_path = config.export_config("/restricted/path")
except PermissionError as e:
    print(f"❌ 権限エラー: {e}")
except OSError as e:
    print(f"❌ ファイルシステムエラー: {e}")
```

---

### メソッド: `import_config(import_file)`

```python
def import_config(self, import_file: str) -> bool
```

**説明:** 外部ファイルから設定をインポート

**パラメータ:**
- `import_file` (str): インポートするファイルパス

**戻り値:** `True`（成功）、`False`（失敗）

**例:**
```python
import_file = "/path/to/rag_agent_config_20260401_120530.json"
success = config.import_config(import_file)

if success:
    print("✅ インポートが完了しました")
else:
    print("❌ インポートに失敗しました")
```

---

### メソッド: `validate_config(config)`

```python
def validate_config(self, config: Dict) -> tuple
```

**説明:** 設定の必須フィールドや値の妥当性を検証

**パラメータ:**
- `config` (Dict): 検証する設定辞書

**戻り値:** タプル `(is_valid: bool, errors: list)`

**例:**
```python
config_dict = config.load_config()
is_valid, errors = config.validate_config(config_dict)

if is_valid:
    print("✅ 設定は有効です")
else:
    print("❌ 設定に問題があります:")
    for error in errors:
        print(f"  {error}")
```

**検証項目:**

1. **必須フィールド:**
   - `llm_model`
   - `search_method`
   - `top_k`
   - `confidence_threshold`
   - `temperature`

2. **値の範囲チェック:**
   - `top_k`: 1-50
   - `confidence_threshold`: 0-1
   - `temperature`: 0-2

**エラーメッセージ例:**
```
❌ 必須フィールドが不足: llm_model
❌ top_k は 1-50 の範囲内である必要があります
❌ confidence_threshold は 0-1 の範囲内である必要があります
```

---

### メソッド: `get_config_summary()`

```python
def get_config_summary(self) -> str
```

**説明:** 現在の設定の概要を整形して出力

**パラメータ:** なし

**戻り値:** 整形されたサマリー文字列

**例:**
```python
summary = config.get_config_summary()
print(summary)
```

**出力例:**
```
📊 RAG Agent 設定サマリー
═══════════════════════════════════════

🤖 モデル設定:
  • LLMモデル: GPT-4o
  • 検索方式: ハイブリッド
  • 言語: ja

🎯 検索パラメータ:
  • 取得ドキュメント数: 5
  • 信頼度閾値: 0.7
  • 対象カテゴリ: root, reports, guides

⚙️ 生成パラメータ:
  • 温度(Temperature): 0.7
  • トークン上限: 2000
  • キャッシュ有効: True

📁 バックアップ先:
  • /mnt/d/backups

✅ 最終更新: 2026-04-01T12:05:30.123456
═══════════════════════════════════════
```

---

## 実装パターン

### パターン1: 基本的な設定管理

```python
from rag_agent_config import RAGAgentConfig

# 初期化
config = RAGAgentConfig()

# 設定の読み込み
current_settings = config.load_config()

# 設定の更新
current_settings['temperature'] = 0.8
current_settings['llm_model'] = 'GPT-4-Turbo'

# 設定の保存
config.save_config(current_settings)

# サマリーの表示
print(config.get_config_summary())
```

### パターン2: 設定の検証付き保存

```python
config = RAGAgentConfig()
settings = config.load_config()

# 設定を変更
settings['top_k'] = 10
settings['temperature'] = 0.6

# 検証してから保存
is_valid, errors = config.validate_config(settings)
if is_valid:
    config.save_config(settings)
    print("✅ 設定を保存しました")
else:
    print("❌ 設定が無効です:")
    for error in errors:
        print(f"  {error}")
```

### パターン3: バックアップとリストア

```python
config = RAGAgentConfig()

# 現在の設定をバックアップ
backup_path = config.backup_config()
print(f"バックアップ作成: {backup_path}")

# 後で復元したいとき
success = config.restore_config()
if success:
    print("✅ 復元完了")

# バックアップ一覧を表示
backups = config.get_backups_list()
for backup in backups:
    print(f"{backup['name']} ({backup['modified']})")
```

### パターン4: エクスポート・インポート

```python
config = RAGAgentConfig()

# 設定をエクスポート
export_path = config.export_config("/mnt/d/backups")
if export_path:
    print(f"エクスポート: {export_path}")

# 別の環境でインポート
import_file = "/mnt/d/backups/rag_agent_config_20260401_120530.json"
success = config.import_config(import_file)
if success:
    print("✅ インポート完了")
```

### パターン5: アプリケーションでの統合

```python
import streamlit as st
from rag_agent_config import RAGAgentConfig

# グローバル変数
config_manager = RAGAgentConfig()

# サイドバーで設定を管理
with st.sidebar.expander("⚙️ 設定"):
    current_config = config_manager.load_config()
    
    llm_model = st.selectbox(
        "LLMモデル",
        ["GPT-4o", "GPT-4", "GPT-3.5"],
        index=0 if current_config['llm_model'] == "GPT-4o" else 1
    )
    
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=current_config['temperature'],
        step=0.1
    )
    
    if st.button("💾 保存"):
        current_config['llm_model'] = llm_model
        current_config['temperature'] = temperature
        config_manager.save_config(current_config)
        st.success("✅ 設定を保存しました")
    
    if st.button("🔐 バックアップ"):
        backup_path = config_manager.backup_config()
        st.success(f"✅ バックアップ: {backup_path}")
```

---

## テスト戦略

### ユニットテストの例

```python
import unittest
from pathlib import Path
import tempfile
import json

from rag_agent_config import RAGAgentConfig

class TestRAGAgentConfig(unittest.TestCase):
    
    def setUp(self):
        """各テストの前に実行"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = RAGAgentConfig(config_dir=self.temp_dir.name)
    
    def tearDown(self):
        """各テストの後に実行"""
        self.temp_dir.cleanup()
    
    def test_load_default_config(self):
        """デフォルト設定の読み込みテスト"""
        config = self.config.load_config()
        self.assertEqual(config['llm_model'], 'GPT-4o')
        self.assertEqual(config['temperature'], 0.7)
    
    def test_save_and_load_config(self):
        """設定の保存と読み込みテスト"""
        original_config = self.config.load_config()
        original_config['temperature'] = 0.9
        
        self.config.save_config(original_config)
        loaded_config = self.config.load_config()
        
        self.assertEqual(loaded_config['temperature'], 0.9)
    
    def test_backup_config(self):
        """バックアップ作成テスト"""
        backup_path = self.config.backup_config()
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())
    
    def test_restore_config(self):
        """リストア機能テスト"""
        # 初期設定
        config = self.config.load_config()
        config['temperature'] = 0.5
        self.config.save_config(config)
        
        # バックアップ作成
        self.config.backup_config()
        
        # 設定を変更
        config['temperature'] = 0.9
        self.config.save_config(config)
        
        # リストア
        self.config.restore_config()
        restored = self.config.load_config()
        
        self.assertEqual(restored['temperature'], 0.5)
    
    def test_validate_config_valid(self):
        """有効な設定の検証テスト"""
        config = self.config.get_default_config()
        is_valid, errors = self.config.validate_config(config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_config_invalid(self):
        """無効な設定の検証テスト"""
        config = self.config.get_default_config()
        config['top_k'] = 100  # 範囲外
        
        is_valid, errors = self.config.validate_config(config)
        
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)

if __name__ == '__main__':
    unittest.main()
```

---

## トラブルシューティング

### 問題1: 「ファイルが見つかりません」エラー

**原因:** `config_dir` が存在しない、または読み込み権限がない

**解決方法:**
```python
from pathlib import Path

# ディレクトリが存在するか確認
config_dir = Path("/home/abemc/project_root/config")
if not config_dir.exists():
    config_dir.mkdir(parents=True, exist_ok=True)

# 読み込み権限を確認
import os
if not os.access(config_dir, os.R_OK):
    print(f"❌ {config_dir} への読み込み権限がありません")
```

### 問題2: JSON パースエラー

**原因:** 設定ファイルが破損している、またはJSON形式が不正

**解決方法:**
```python
# バックアップから復元
config = RAGAgentConfig()
success = config.restore_config()
if success:
    print("✅ バックアップから復元しました")
else:
    print("❌ バックアップがありません")
    # デフォルト設定を使用
    config.save_config(config.get_default_config())
```

### 問題3: 設定の検証エラー

**原因:** 設定値が指定の範囲外

**解決方法:**
```python
config = RAGAgentConfig()
settings = config.load_config()

# 無効な値を修正
if settings['top_k'] > 50:
    settings['top_k'] = 50

if settings['temperature'] > 2:
    settings['temperature'] = 2

# 検証
is_valid, errors = config.validate_config(settings)
if is_valid:
    config.save_config(settings)
```

---

## ベストプラクティス

### 1. 常に検証してから保存

```python
# ❌ 悪い例
config_dict['top_k'] = 100
config.save_config(config_dict)

# ✅ 良い例
config_dict['top_k'] = 100
is_valid, errors = config.validate_config(config_dict)
if is_valid:
    config.save_config(config_dict)
else:
    print("❌ 設定エラー:", errors)
```

### 2. 定期的にバックアップを作成

```python
# ✅ 推奨
config.backup_config()  # 重要な変更の後
```

### 3. 例外処理を実装

```python
# ✅ 推奨
try:
    config.save_config(settings)
except Exception as e:
    logger.error(f"設定保存エラー: {e}")
    # フォールバック処理
```

### 4. 設定値の範囲に注意

```python
# ✅ 推奨
VALID_RANGES = {
    'top_k': (1, 50),
    'temperature': (0.0, 2.0),
    'confidence_threshold': (0.0, 1.0)
}

for key, (min_val, max_val) in VALID_RANGES.items():
    value = config_dict.get(key)
    if value is not None:
        config_dict[key] = max(min_val, min(value, max_val))
```

### 5. ログを記録

```python
import logging

logger = logging.getLogger(__name__)

config = RAGAgentConfig()
logger.info("設定を読み込みました")

config.save_config(settings)
logger.info("設定を保存しました")
```

---

**ドキュメント作成日**: 2026-04-26  
**バージョン**: 1.0
