# Phase 11 Week 2 Day 2-5 実装ガイド

**対象期間**: 2026-04-20 ～ 2026-04-23  
**目標**: 実モデル推論統合 + 多言語対応  
**予想成果**: 精度向上 (MMLU 10-15%, GSM8K 5-10%)

---

## 📋 Day 2-3: 実モデル推論統合

### 背景

現在、`baseline_measurement.py` はダミー推論を使用しており、精度が非常に低い状態です:
- MMLU: 2% (ダミー)
- GSM8K: 0% (ダミー)

Day 2-3では、実際のモデルチェックポイントを読込み、真の推論を実行します。

### タスク 1: チェックポイント読込実装

**ファイル**: `src/evaluation/model_loader.py` (新規作成)

```python
import torch
from pathlib import Path
from model import GPT, GPTConfig

class ModelCheckpointLoader:
    """モデルチェックポイント読込エンジン"""
    
    def __init__(self, device='cpu'):
        self.device = device
    
    def load_checkpoint(self, checkpoint_path):
        """
        チェックポイントからモデルを読込
        
        Args:
            checkpoint_path: チェックポイントファイルのパス
            
        Returns:
            GPTモデルインスタンス
        """
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        
        # ConfigとStateを抽出
        config = checkpoint.get('config', self._default_config())
        
        # モデル生成
        model = GPT(config)
        model.to(self.device)
        
        # 重み読込
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        
        model.eval()  # 評価モード
        return model
    
    def _default_config(self):
        """デフォルト設定"""
        return GPTConfig(
            vocab_size=50257,
            n_layers=6,
            n_heads=8,
            embedding_dim=256
        )
```

**チェックポイント探索**:

```bash
# プロジェクト内のチェックポイントを確認
find /home/abemc/project_root -name "*.pt" -o -name "*.pth" | head -20

# checkpoints/ ディレクトリの確認
ls -la /home/abemc/project_root/checkpoints/
```

### タスク 2: トークン化パイプライン実装

**ファイル**: `src/evaluation/tokenizer_pipeline.py` (新規作成)

```python
class TokenizerPipeline:
    """トークン化・デトークン化パイプライン"""
    
    def __init__(self, vocab_size=50257):
        self.vocab_size = vocab_size
    
    def encode(self, text):
        """テキストをトークンに変換"""
        # シンプル実装: 文字ベースのトークン化
        tokens = [ord(c) % self.vocab_size for c in text]
        return torch.tensor(tokens)
    
    def decode(self, tokens):
        """トークンをテキストに変換"""
        # シンプル実装
        text = ''.join(chr(t.item() % 256) for t in tokens if t < 256)
        return text
    
    def batch_encode(self, texts, max_length=512):
        """バッチエンコード"""
        encoded = []
        for text in texts:
            tokens = self.encode(text)
            if len(tokens) > max_length:
                tokens = tokens[:max_length]
            encoded.append(tokens)
        
        # パディング
        return self._pad_sequences(encoded)
    
    def _pad_sequences(self, sequences):
        """シーケンスをパディング"""
        max_len = max(len(s) for s in sequences)
        padded = []
        for s in sequences:
            if len(s) < max_len:
                s = torch.cat([s, torch.zeros(max_len - len(s))])
            padded.append(s)
        return torch.stack(padded)
```

### タスク 3: 推論関数置換

**ファイル**: `src/evaluation/baseline_measurement.py` (修正)

現在のダミー実装:

```python
def predict_classification(self, prompt, choices):
    # ダミー: プロンプト長に基づいた選択
    pred_idx = len(prompt) % len(choices)
    return choices[pred_idx]
```

新しい実装:

```python
def predict_classification(self, prompt, choices):
    """MMLU分類予測 (実推論)"""
    
    # トークン化
    tokens = self.tokenizer.encode(prompt)
    tokens = tokens.unsqueeze(0).to(self.device)
    
    # 推論
    with torch.no_grad():
        logits = self.model(tokens)
    
    # 最後のトークンの次のトークンを予測
    next_token_logits = logits[0, -1, :]
    
    # 選択肢の最初の文字に対応するトークンのスコア
    choice_scores = []
    for choice in choices:
        choice_token = self.tokenizer.encode(choice[0])[0]
        score = next_token_logits[choice_token].item()
        choice_scores.append(score)
    
    # 最高スコアの選択肢を返す
    best_idx = np.argmax(choice_scores)
    return choices[best_idx]
```

### テストスクリプト

```bash
# Day 2-3の実装テスト
python << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, 'src')

from evaluation.model_loader import ModelCheckpointLoader
from evaluation.tokenizer_pipeline import TokenizerPipeline
from evaluation.baseline_measurement import BaselineMeasurementRunner

# チェックポイント読込
loader = ModelCheckpointLoader(device='cpu')
checkpoint_path = 'checkpoints/ckpt_step_2499.pt'
model = loader.load_checkpoint(checkpoint_path)
print(f"✅ Model loaded: {model}")

# パイプライン構築
runner = BaselineMeasurementRunner(
    checkpoint_path=checkpoint_path,
    output_dir='results/benchmarks/week2_day2',
    device='cpu'
)

# MMLU測定
print("\nTesting MMLU with real inference...")
result = runner.measure_mmlu_with_cot(num_samples=10)
print(f"MMLU Accuracy: {result['metrics']['accuracy']:.4f}")

# GSM8K測定
print("\nTesting GSM8K with real inference...")
result = runner.measure_gsm8k_with_cot(num_samples=5)
print(f"GSM8K Accuracy: {result['metrics']['accuracy']:.4f}")
EOF
```

---

## 📋 Day 4-5: 多言語対応

### タスク 1: 日本語ベンチマーク追加

**ファイル**: `src/evaluation/datasets/japanese_benchmarks.py` (新規作成)

```python
class JapaneseMMULoader:
    """日本語MMLU相当のベンチマーク"""
    
    def __init__(self, num_samples=50):
        self.num_samples = num_samples
        self.questions = []
    
    def load(self):
        """日本語問題をロード"""
        # サンプル質問
        self.questions = [
            {
                'question': '以下の文で最も適切な選択肢は?',
                'choices': ['A', 'B', 'C', 'D'],
                'answer': 'A'
            },
            # 追加...
        ]
        return self.questions

class JapanMathProblemLoader:
    """日本語数学問題ベンチマーク"""
    
    def __init__(self, difficulty='elementary'):
        self.difficulty = difficulty
    
    def load(self):
        """日本語数学問題をロード"""
        problems = [
            {
                'problem': 'ジェーンは3個のリンゴを持っています。さらに2個買いました。全部で何個?',
                'answer': '5'
            },
            # 追加...
        ]
        return problems
```

### タスク 2: 日本語プロンプト最適化

**ファイル**: `src/evaluation/cot_reasoning.py` (修正)

現在:

```python
MMLU_COT = """
Question: {question}
Options: {options}
...
"""
```

新しい実装:

```python
MMLU_COT_JA = """
問題: {question}

選択肢:
{options}

段階を踏んで考えてみます:
1. この問題が何を聞いているか理解する
2. 各選択肢を慎重に分析する
3. 知識を使って正解を決定する

段階的な推論:
{reasoning}

正しい答えは: """

JAPANESE_GSM8K_COT = """
問題: {problem}

段階を踏んで解いてみます:

ステップ1: この問題が求めていることを理解する
- 探す対象: {what_to_find}

ステップ2: 与えられた情報を整理する
- 与えられた情報: {given_info}

ステップ3: 解く方法を計画する
- 方針: {strategy}

ステップ4: 段階的に解く
{solution_steps}

ステップ5: 答えを確認する
- 答えが妥当である理由: {verification}

したがって、答えは: """
```

### テストスクリプト

```bash
# Day 4-5の実装テスト
python << 'EOF'
from src.evaluation.datasets.japanese_benchmarks import (
    JapaneseMMULoader,
    JapanMathProblemLoader
)
from src.evaluation.cot_reasoning import PromptOptimizer

# 日本語ローダー
jp_mmu = JapaneseMMULoader(num_samples=20)
jp_math = JapanMathProblemLoader()

jp_mmu_q = jp_mmu.load()
jp_math_p = jp_math.load()

print(f"✅ Japanese MMLU: {len(jp_mmu_q)} questions")
print(f"✅ Japanese Math: {len(jp_math_p)} problems")

# 日本語プロンプト最適化
optimizer = PromptOptimizer()
result = optimizer.optimize_for_language("Let me think", "ja")
print(f"✅ Optimized prompt: {result}")
EOF
```

---

## 🔧 実装上の注意点

### 1. GPU/CPU選択

```python
# GPUが利用可能か確認
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Device: {device}")
```

### 2. メモリ管理

```python
# メモリ効率的な推論
with torch.no_grad():
    with torch.cuda.amp.autocast():  # 混精度推論
        outputs = model(inputs)
```

### 3. キャッシング

```python
# 同じ入力への重複計算を避ける
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_inference(prompt_hash):
    # 推論結果をキャッシュ
    pass
```

### 4. エラーハンドリング

```python
# チェックポイント読込失敗時のフォールバック
try:
    model = loader.load_checkpoint(checkpoint_path)
except:
    print("Falling back to random model")
    model = GPT(default_config)
```

---

## 📊 期待される改善

### メトリクス改善予測

| ベンチマーク | 現在 | Day 2-3後 | Day 4-5後 |
|-----------|------|---------|---------|
| **MMLU** | 2% | 5-10% | 10-15% |
| **GSM8K** | 0% | 2-5% | 5-10% |
| **日本語** | N/A | N/A | 準備完了 |

### 実装工数予測

| タスク | 予想時間 | 実装方法 |
|--------|---------|---------|
| チェックポイント読込 | 30分 | Torch checkpoint |
| トークン化パイプライン | 1時間 | シンプル実装 |
| 推論関数置換 | 1.5時間 | モジュール置換 |
| テスト・検証 | 1時間 | 単位テスト |
| **Day 2-3 合計** | **4時間** | |
| 日本語対応 | 3時間 | サンプル追加 |
| プロンプト最適化 | 1.5時間 | テンプレート拡張 |
| テスト・測定 | 1.5時間 | 実行検証 |
| **Day 4-5 合計** | **6時間** | |

---

## ✅ チェックリスト

### Day 2-3チェックリスト
- [ ] モデルローダー実装
- [ ] トークナイザー実装
- [ ] 推論関数置換
- [ ] ユニットテスト実行
- [ ] MMLU測定実行
- [ ] GSM8K測定実行
- [ ] 結果記録 (JSON)

### Day 4-5チェックリスト
- [ ] 日本語ローダー実装
- [ ] 日本語プロンプト追加
- [ ] 言語別最適化テスト
- [ ] 全言語での測定実行
- [ ] 結果比較分析
- [ ] Week 2完成レポート作成

---

## 📞 トラブルシューティング

### 問題: チェックポイントが見つからない

```bash
# checkpoints/ ディレクトリの確認
ls -lh /home/abemc/project_root/checkpoints/

# 最新のチェックポイント検索
find . -name "*.pt" -mtime -1  # 1日以内に変更
```

### 問題: OOM (メモリ不足)

```python
# バッチサイズ削減
runner.measure_mmlu_with_cot(num_samples=5)  # 50から削減

# 勾配計算無効化
with torch.no_grad():
    output = model(input)
```

### 問題: トークン化エラー

```python
# シンプルなトークナイザーテスト
text = "Hello, world!"
tokens = tokenizer.encode(text)
decoded = tokenizer.decode(tokens)
assert text in decoded, "Tokenization failed"
```

---

## 🚀 実行コマンド

### Day 2-3 開始

```bash
cd /home/abemc/project_root

# 新規ファイル作成
touch src/evaluation/model_loader.py
touch src/evaluation/tokenizer_pipeline.py

# 実装テスト
python tests/test_model_loader.py
python tests/test_tokenizer_pipeline.py
```

### Day 4-5 開始

```bash
# 日本語対応ファイル作成
touch src/evaluation/datasets/japanese_benchmarks.py

# プロンプト拡張
python tests/test_japanese_prompts.py

# 全測定実行
python src/evaluation/measure_cot_performance.py --all
```

---

## 📋 成果確認

### Week 2完成時の確認事項

```bash
# 1. コード行数
wc -l src/evaluation/*.py | tail -1  # 3,000行以上?

# 2. テスト合格
pytest tests/ -v  # 全テスト合格?

# 3. 結果データ
cat results/benchmarks/cot_measurements.json | jq .  # JSON形式OK?

# 4. ドキュメント
ls -l docs/reports/ | grep Phase11  # レポート4本揃ってる?
```

---

**ガイド作成日**: 2026-04-19  
**対象実装期間**: 2026-04-20 ～ 2026-04-23  
**次回の報告**: 2026-04-23 (Week 2完成時)
