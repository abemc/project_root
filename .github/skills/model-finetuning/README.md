# Model Finetuning スキル

このスキルは、プロジェクトのモデル微調整ワークフローを標準化し、特にデータセット検証とエラー対処に重点を置いています。

## ファイル構成

```
.github/skills/model-finetuning/
├── SKILL.md                      # メインの手順書
├── scripts/
│   ├── validate_dataset.py       # データセット検証ツール
│   └── manage_checkpoints.py     # チェックポイント管理ツール
└── references/
    └── troubleshooting.md        # トラブルシューティングガイド
```

## 使い方

### 1. データセット検証

微調整を開始する前に、必ずデータセットを検証してください：

```bash
cd /home/abemc/project_root
python .github/skills/model-finetuning/scripts/validate_dataset.py
```

または、カスタムパスを指定：

```bash
python .github/skills/model-finetuning/scripts/validate_dataset.py /path/to/dataset.jsonl
```

**期待される出力:**
```
Dataset file: /mnt/d/rag_corpus/dataset.jsonl
File size: 45.32 MB
------------------------------------------------------------
✓ Valid lines: 1,234
✗ Invalid lines: 0
✓ Estimated tokens: 247,000
------------------------------------------------------------
✓ Dataset validation passed! No errors found.
```

### 2. チェックポイント確認

訓練開始前に、既存チェックポイントを確認：

```bash
python .github/skills/model-finetuning/scripts/manage_checkpoints.py list
```

**出力例:**
```
Training Checkpoints
============================================================
  Step   200: ckpt_step_200.pt                  (145.3 MB)
  Step   400: ckpt_step_400.pt                  (145.3 MB)
  Step  1000: ckpt_step_1000.pt                 (145.3 MB)
============================================================
Latest checkpoint: Step 1000
Training will resume from step 1000
```

### 3. 訓練実行

```bash
source .venv/bin/activate
python -m src.train_gpt
```

### 4. トラブルシューティング

エラーが発生した場合、[troubleshooting.md](references/troubleshooting.md) を参照してください。

## よくある使用ケース

### 新しいデータセットで訓練を開始

```bash
# 1. データセットの検証
python .github/skills/model-finetuning/scripts/validate_dataset.py

# 2. （必要に応じて）パラメータ調整
# → src/train_gpt.py のハイパーパラメータを確認

# 3. 古いチェックポイントをリセット
rm checkpoints/*.pt

# 4. 訓練開始
python -m src.train_gpt
```

### 以前の訓練から再開

```bash
# 1. 最新チェックポイント確認
python .github/skills/model-finetuning/scripts/manage_checkpoints.py latest

# 2. 訓練再開（自動的に最新から再開）
python -m src.train_gpt
```

### データセット形式エラーの診断

```bash
# 1. 詳細な検証を実行
python .github/skills/model-finetuning/scripts/validate_dataset.py

# 2. troubleshooting.md の「データセット関連のエラー」を参照

# 3. 必要に応じてデータセットを再生成
python manage_kb.py --action=rebuild
```

## パラメータカスタマイズ

主要なハイパーパラメータは [src/train_gpt.py](../../../../src/train_gpt.py) で定義されています：

| パラメータ | デフォルト | 説明 |
|----------|---------|------|
| `batch_size` | 12 | バッチサイズ（メモリ不足なら減らす） |
| `block_size` | 512 | コンテキスト長 |
| `max_iters` | 2500 | 訓練ステップ数 |
| `learning_rate` | 3e-4 | 学習率 |
| `n_layer` | 6 | トランスフォーマーの層数 |
| `n_head` | 6 | マルチヘッドアテンション数 |
| `n_embd` | 384 | 埋め込み次元 |

## エラーの95%はデータセット形式

このスキルに含まれるツールる主にデータセット検証に重点を置いているのは、経験から訓練エラーの95%がデータセット形式に起因するためです。

**必ずチェック:**
1. ✅ ファイルが存在するか
2. ✅ JSON 形式は有効か
3. ✅ 各行に `"text"` フィールドがあるか
4. ✅ `text` 値は空でない文字列か

これらをすべてク確認できれば、訓練エラーのほとんどは解決されます。

## 参考資料

- [SKILL.md](SKILL.md) - 詳細な手順書
- [troubleshooting.md](references/troubleshooting.md) - トラブルシューティング
- [src/train_gpt.py](../../../../src/train_gpt.py) - 訓練スクリプト
- [src/train/configs.py](../../../../src/train/configs.py) - モデル設定

## 次のステップ

訓練完了後：
1. モデルを `fine_tuned_model/` に保存
2. テストセットで評価
3. 推論テストを実行
