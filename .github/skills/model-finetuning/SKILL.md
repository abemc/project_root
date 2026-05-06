---
name: model-finetuning
description: "モデル微調整ワークフロー。データセット検証、ハイパーパラメータ設定、訓練実行、チェックポイント管理。Use when: モデルの微調整を行う、データセット形式エラーをデバッグ、訓練状態から再開する。"
argument-hint: "検証または訓練を実行するデータセットパス（オプション）"
---

# モデル微調整スキル

このスキルは、プロジェクトのモデル微調整プロセスを標準化します。特にデータセット準備の検証とデータ形式エラーの診断に重点を置いています。

## いつ使うか

- 新しいデータセットで微調整を開始する
- 「データセット形式」エラーが発生した
- チェックポイントから訓練を再開する
- 訓練パラメータを変更する

## 前提条件

- Python 環境が有効 (`.venv/bin/activate` で初期化済み)
- `src/train_gpt.py` と `src/train/configs.py` が配置されている
- `dataset.jsonl` が `CORPUS_ROOT` に存在する

## ステップバイステップ手順

### 1. データセット検証（最初に必ず実行）

データセット形式エラーを防ぐため、まずデータを検証します。

```python
# データセット検証スクリプト
import json
from pathlib import Path

DATASET_PATH = Path("/mnt/d/rag_corpus/dataset.jsonl")

# ファイルが存在するか確認
if not DATASET_PATH.exists():
    raise FileNotFoundError(f"∃ dataset not found: {DATASET_PATH}")

# ファイルサイズを確認
file_size_mb = DATASET_PATH.stat().st_size / (1024 * 1024)
print(f"Dataset size: {file_size_mb:.2f} MB")

# 行数とデータ形式を検証
valid_lines = 0
invalid_lines = 0
errors = []

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        try:
            data = json.loads(line)
            # 必須フィールド確認
            if "text" not in data:
                invalid_lines += 1
                errors.append(f"Line {line_num}: missing 'text' field")
                continue
            if not isinstance(data["text"], str) or len(data["text"]) == 0:
                invalid_lines += 1
                errors.append(f"Line {line_num}: 'text' is not a non-empty string")
                continue
            valid_lines += 1
        except json.JSONDecodeError as e:
            invalid_lines += 1
            errors.append(f"Line {line_num}: JSON parse error: {e}")

print(f"\n✓ Valid lines: {valid_lines}")
print(f"✗ Invalid lines: {invalid_lines}")

if errors:
    print(f"\nFirst 5 errors:")
    for err in errors[:5]:
        print(f"  - {err}")
else:
    print("\n✓ All lines are valid!")

# トークンサイズの推定
print(f"\nEstimated tokens (using tiktoken cl100k_base): ~{valid_lines * 200} tokens")
```

**想定結果:**
- すべて `✓ Valid lines` に含まれるべき
- エラーがある場合は、項目「よくあるエラーと対処法」を参照

### 2. ハイパーパラメータの確認と調整

[src/train_gpt.py](../../../../src/train_gpt.py) の以下のセクションを確認:

```python
batch_size = 12        # VRAMに応じて調整 (不足なら減らす)
block_size = 512       # コンテキスト長
max_iters = 2500       # 学習ステップ数
learning_rate = 3e-4   # 学習率
n_embd = 384           # 埋め込み次元
n_head = 6             # Attentionヘッド数
n_layer = 6            # レイヤー数
eval_interval = 200    # 評価ログ出力間隔
```

**チェックリスト:**
- [ ] VRAM容量に対して `batch_size` が適切か？（OOMエラーなら減らす）
- [ ] GPU利用可能か？ (`torch.cuda.is_available()` で確認)
- [ ] `max_iters` は試験的なら小さく（例: 200）、本格的なら大きく（例: 2500）

### 3. 前回チェックポイントの確認

```python
from pathlib import Path

CHECKPOINT_DIR = Path("checkpoints")
if CHECKPOINT_DIR.exists():
    ckpts = sorted(CHECKPOINT_DIR.glob("ckpt_step_*.pt"))
    if ckpts:
        latest = ckpts[-1]
        step = int(latest.stem.split("_")[-1])
        print(f"Latest checkpoint: {latest.name} (Step {step})")
    else:
        print("No checkpoints found. Starting fresh.")
else:
    print("Checkpoint directory does not exist. Will be created on first run.")
```

**判断:**
- チェックポイントがある → 続きから再開される（自動）
- ない → 最初から訓練開始

### 4. 訓練実行

```bash
cd /home/abemc/project_root
source .venv/bin/activate
python -m src.train_gpt
```

**監視ポイント:**
- 最初の 2-3 ステップで loss が低下しているか？
- train loss > val loss の傾向が正常
- `eval_interval` ごとにログが出力される

**中止したい場合:** `Ctrl+C` で安全に停止（次のチェックポイントから再開可能）

## よくあるエラーと対処法

### ❌ `FileNotFoundError: Dataset not found`

**原因:** `dataset.jsonl` のパスが間違っている

**対処:**
1. `CORPUS_ROOT` の値を確認: [src/train_gpt.py#L34](../../../../src/train_gpt.py#L34)
2. 対象ディレクトリが存在するか確認:
   ```bash
   ls -la /mnt/d/rag_corpus/
   ```
3. ファイルが存在するか確認:
   ```bash
   ls -lh /mnt/d/rag_corpus/dataset.jsonl
   ```

### ❌ `json.JSONDecodeError: ... in dataset.jsonl`

**原因:** JSONL ファイルのフォーマットが不正（改行がない、形式が違うなど）

**対処:**
1. ファイルの先頭行を確認:
   ```bash
   head -1 /mnt/d/rag_corpus/dataset.jsonl | python -m json.tool
   ```
2. 有効な JSON か確認（上記コマンド実行後、結構化データが出力されるか確認）
3. **形式が違う場合** → `build_knowledge.py` や `manage_kb.py` で再生成

### ❌ `missing 'text' field in dataset`

**原因:** JSONL の各行に `"text"` キーがない

**対処:**
1. データセットの構造を確認:
   ```bash
   head -5 /mnt/d/rag_corpus/dataset.jsonl | python -c "
   import sys, json
   for line in sys.stdin:
       obj = json.loads(line)
       print('Keys:', list(obj.keys()))
       break
   "
   ```
2. 期待される構造:
   ```json
   {"text": "...", "metadata": {...}}
   ```
3. 異なる構造の場合 → データセット生成スクリプトを確認・修正

### ❌ `CUDA out of memory (OOM)`

**原因:** `batch_size` が GPU メモリを超えている

**対処:**
1. `batch_size` を減らす: `6` → `4` → `2`
2. `block_size` を減らす: `512` → `256`（トークンシーケンス長）
3. 確認:
   ```bash
   nvidia-smi  # GPU メモリ状況確認
   ```

### ❌ `Model parameters mismatch` (チェックポイント再開時)

**原因:** ハイパーパラメータを変更したが、古いチェックポイントから読み込もうとしている

**対処:**
1. パラメータを変更した場合は、チェックポイントを削除:
   ```bash
   rm checkpoints/*.pt
   ```
2. または、パラメータを前回と同じ値に戻す

## パラメータ設定ガイド

[src/train/configs.py](../../../../src/train/configs.py) で定義済みの設定:

| 設定名 | パラメータ | 用途 |
|------|----------|------|
| `small_124M` | 12層、768次元 | テスト・軽量 |
| `medium_355M` | 24層、1024次元 | 標準 |
| `math_700M` | 32層、1280次元 | 数学特化・大規模 |

**選択方法:**
- GPU メモリ < 8GB → `small_124M`
- GPU メモリ 8-16GB → `medium_355M`
- GPU メモリ > 16GB → `math_700M`

## チェックポイント管理

```bash
# 過去のチェックポイント一覧
ls -lh checkpoints/

# 最新のステップを取得
ls -t checkpoints/ckpt_step_*.pt | head -1 | sed 's/.*_\([0-9]*\)\.pt/\1/'

# 特定ステップから再開したい場合
# → パラメータ変更なしで src.train_gpt を実行すれば自動的に最新から再開
```

## 訓練進度の監視

[logs/history.jsonl](../../../../logs/history.jsonl) に実行履歴が保存されます。

```python
import json

with open("logs/history.jsonl", "r") as f:
    history = [json.loads(line) for line in f]
    for entry in history[-5:]:  # 最後の5件
        print(f"Iteration {entry.get('iteration')}: Loss = {entry.get('loss')}")
```

## 次のステップ

- 訓練完了後: `fine_tuned_model/` にモデルを保存
- 評価: テストセットで性能測定
- 推론: 微調整済みモデルで実際の推論テスト
