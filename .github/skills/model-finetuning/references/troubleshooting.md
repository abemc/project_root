# トラブルシューティングリファレンス

## データセット関連のエラー

### JSON 形式エラー

**症状:**
```
json.JSONDecodeError: Expecting value: line X column Y
```

**原因:**
1. JSONL の行が不完全（改行がない）
2. JSON 内に制御文字や無効なエスケープシーケンス
3. ファイルエンコーディングが UTF-8 でない

**チェック:**
```bash
# ファイルエンコーディングを確認
file /mnt/d/rag_corpus/dataset.jsonl

# 最初の1行をテスト
head -1 /mnt/d/rag_corpus/dataset.jsonl | python -m json.tool

# 問題のある行を特定
python3 -c "
import json
from pathlib import Path
path = Path('/mnt/d/rag_corpus/dataset.jsonl')
with open(path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except:
            print(f'Error at line {i}')
            print(repr(line[:200]))
            break
"
```

**解決:**
1. JSONL 再生成: `python manage_kb.py --action=rebuild`
2. ファイルを UTF-8 に変換: `iconv -f ISO-8859-1 -t UTF-8 dataset.jsonl > dataset_utf8.jsonl`

---

### 必須フィールド不足エラー

**症状:**
```
Line X: missing 'text' field
```

**原因:**
- JSONL の各行に `"text"` キーがない
- データセット生成方式が異なる

**確認コマンド:**
```bash
# 実際のキーを確認
head -5 /mnt/d/rag_corpus/dataset.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    obj = json.loads(line)
    print('Keys:', sorted(obj.keys()))
"
```

**解決:**
1. データセット生成スクリプトを確認: `cat load_prompt.py`
2. 形式を変換する前処理を作成
3. または、データセット再生成

---

## メモリ関連のエラー

### CUDA OOM エラー

**症状:**
```
RuntimeError: CUDA out of memory. Tried to allocate X.XXGiB
```

**原因:**
- `batch_size` が GPU メモリを超えている
- `block_size` が大きすぎる
- 他のプロセスが GPU を使用中

**確認コマンド:**
```bash
# GPU メモリ使用状況
nvidia-smi

# プロセス詳細
nvidia-smi -pm 1

# 他のプロセスを確認
lsof /dev/nvidia*
```

**段階的な対処:**
1. `batch_size` を 12 → 6 に減らす
2. `batch_size` を 6 → 4 に減らす
3. `batch_size` を 4 → 2 に減らす
4. `block_size` を 512 → 256 に減らす

**src/train_gpt.py での修正:**
```python
batch_size = 6        # 12 から 6 に変更
block_size = 256      # 512 から 256 に変更
```

---

## チェックポイント関連のエラー

### モデルパラメータ不一致エラー

**症状:**
```
size mismatch for transformer.h.0.attn.c_attn.weight
```

**原因:**
- ハイパーパラメータを変更してから、古いチェックポイントから再開しようとしている
- 例: `n_layer` を 6 から 12 に変更したが、古いチェックポイントは 6 層

**確認:**
```bash
# 現在のパラメータを確認
grep "^n_layer\|^n_head\|^n_embd" src/train_gpt.py

# チェックポイントの層数を確認
python3 -c "
import torch
ckpt = torch.load('checkpoints/ckpt_step_1000.pt', weights_only=True)
# transformer.h.0, transformer.h.1... の数を数える
layers = max(int(k.split('.')[2]) for k in ckpt.keys() if 'transformer.h' in k) + 1
print(f'Checkpoint has {layers} layers')
"
```

**解決:**
1. **オプション1: パラメータを戻す**
   - 変更したパラメータを前回と同じ値に戻す
   
2. **オプション2: チェックポイントをリセット**
   ```bash
   rm checkpoints/*.pt
   # これで最初から訓練が開始されます
   ```

3. **オプション3: 新しいパラメータで継続**
   - (高度) チェックポイント互換性ツールを使用（別途実装が必要）

---

## 訓練が進まないエラー

**症状:**
- `loss: nan` または `loss: inf`
- Loss が減少しない
- 訓練が極端に遅い

### NaN Loss

**原因:**
- 学習率が高すぎる
- 勾配爆発
- データに無限値や NaN 値が含まれている

**対処:**
```python
# src/train_gpt.py で学習率を下げる
learning_rate = 1e-4  # 3e-4 から 1e-4 に下げる
```

### Loss が減少しない

**原因:**
1. データセット品質が悪い
2. 学習率が低すぎる
3. モデル容量が不足

**チェック:**
```bash
# データサンプルを確認
python3 -c "
import json
with open('/mnt/d/rag_corpus/dataset.jsonl') as f:
    for _ in range(3):
        obj = json.loads(next(f))
        print(obj['text'][:200])
        print('---')
"
```

**対処:**
1. データセットの品質を改善
2. 学習率を上げてみる: 3e-4 → 5e-4
3. より大きなモデルを使う: `medium_355M` を試す

### 訓練が遅い

**原因:**
- GPU を使用していない（CPU で実行中）
- バッチサイズが小さすぎる（逆説的だが、小さすぎると遅い）

**確認:**
```bash
# GPU 使用状況
nvidia-smi

# 実行中のスクリプトがGPUを使用しているか
# → src/train_gpt.py の出力に "Using device: cuda" と表示されるか確認
```

---

## 環境関連のエラー

### モジュール不見つかエラー

**症状:**
```
ModuleNotFoundError: No module named 'tiktoken'
```

**原因:**
- 仮想環境が有効になっていない
- 必要なパッケージがインストールされていない

**対処:**
```bash
# 仮想環境を有効化
source /home/abemc/project_root/.venv/bin/activate

# パッケージをインストール
pip install -r requirements.txt

# 確認
python -c "import tiktoken; print('OK')"
```

### PyTorch のデバイスエラー

**症状:**
```
RuntimeError: Expected all tensors to be on the same device
```

**原因:**
- CPU 上のテンソルと GPU 上のテンソルを混用している

**確認:**
```python
# src/train_gpt.py で以下を実行
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Device: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
```

---

## パフォーマンス チューニング

### メモリ使用量を削減

```python
# src/train_gpt.py
batch_size = 4          # 小さくする
block_size = 256        # 短くする
n_layer = 6             # 浅くする
n_head = 4              # ヘッド数を減らす
dropout = 0.3           # ドロップアウト率を増やす
```

### 訓練速度を向上

```python
# src/train_gpt.py
batch_size = 32         # 大きくする（メモリに余裕がある場合）
eval_interval = 500     # 評価頻度を下げる
eval_iters = 50         # 評価ステップ数を減らす
```

---

## デバッグ用ユーティリティ

### データセット検証

```bash
python .github/skills/model-finetuning/scripts/validate_dataset.py /mnt/d/rag_corpus/dataset.jsonl
```

### チェックポイント確認

```bash
python .github/skills/model-finetuning/scripts/manage_checkpoints.py list
python .github/skills/model-finetuning/scripts/manage_checkpoints.py info checkpoints/ckpt_step_1000.pt
```

### 訓練ログ確認

```bash
# 最新ログを表示
tail -f logs/history.jsonl

# 損失値の推移を確認
python -c "
import json
with open('logs/history.jsonl') as f:
    lines = [json.loads(line) for line in f]
    for entry in lines[-10:]:
        print(f\"Step {entry['step']}: loss={entry.get('loss', 'N/A')}\")"
```
