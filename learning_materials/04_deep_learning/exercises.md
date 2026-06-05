# 演習: ディープラーニング 基礎

## 演習 1 — テンソル操作と自動微分

**目標**: PyTorch のテンソル操作と autograd の基礎を確認する。

1. 形状 `(3, 4)` のランダムテンソル `A` と `(4, 2)` のランダムテンソル `B` を作成し、行列積を計算する
2. $f(x) = x^3 - 2x^2 + x$ について `x = 2.0` での $df/dx$ を autograd で計算し、解析解（$3x^2 - 4x + 1 = 5$）と一致を確認する
3. 以下の関数を実装して勾配を確認する:

$$L(\mathbf{w}) = \frac{1}{N}\sum_{i=1}^{N}(y_i - \mathbf{w}^T \mathbf{x}_i)^2$$

```python
torch.manual_seed(42)
X = torch.randn(100, 3)
w_true = torch.tensor([1.0, -2.0, 0.5])
y = X @ w_true + torch.randn(100) * 0.1

w = torch.zeros(3, requires_grad=True)
# ↑ ここから: L を計算し、w の勾配を求めよ
```

---

## 演習 2 — MLP で Iris 分類

**目標**: `nn.Module` を継承した MLP を実装して Iris を 3 クラス分類する。

**要件:**
1. `IrisDataset`（`torch.utils.data.Dataset`）を実装する
2. 以下の構造の MLP を実装する:
   ```
   Linear(4→32) → ReLU → Dropout(0.2) → Linear(32→16) → ReLU → Linear(16→3)
   ```
3. `Adam` オプティマイザ、`CrossEntropyLoss` を使って 100 エポック訓練する
4. エポックごとに訓練損失と検証精度を記録してプロットする
5. 最終的な精度を `sklearn.metrics.classification_report` で表示する

---

## 演習 3 — 簡易 CNN で手書き数字分類

**目標**: CNN を実装して MNIST 風データ（FashionMNIST）を分類する。

```python
from torchvision import datasets, transforms

transform = transforms.Compose([transforms.ToTensor(),
                                 transforms.Normalize((0.5,), (0.5,))])
train_ds = datasets.FashionMNIST("./data", train=True, download=True, transform=transform)
test_ds  = datasets.FashionMNIST("./data", train=False, download=True, transform=transform)
```

**要件:**
1. `SimpleCNN` を実装する（Conv2d × 2 + MaxPool + Flatten + Linear × 2）
2. バッチサイズ 64 で `DataLoader` を作成する
3. 5 エポック訓練し、テスト精度 ≥ 85% を目標にする
4. 誤分類したサンプルを 5 枚表示して傾向を分析する

---

## 演習 4 — 学習率スケジューラの比較

**目標**: 異なる学習率スケジューラが収束速度に与える影響を理解する。

演習 2 または 3 のモデルを再利用し、以下を比較する:

| スケジューラ | PyTorch クラス | 設定 |
|---|---|---|
| 固定 LR | なし | `lr=0.001` |
| Step Decay | `StepLR` | `step_size=30, gamma=0.1` |
| Cosine Annealing | `CosineAnnealingLR` | `T_max=100` |
| Reduce on Plateau | `ReduceLROnPlateau` | `patience=10` |

- 各スケジューラで 100 エポック訓練し、損失曲線と最終精度を比較する

---

## 演習 5 — 正則化テクニックの比較（発展）

**目標**: Dropout・BatchNorm・Weight Decay の効果を過学習を通して理解する。

**設定**: 小さな訓練データ（200 サンプル）+ 大きな検証データで故意に過学習させる。

1. 正則化なしの大きな MLP を訓練し、訓練/検証損失のギャップを確認する
2. 以下を一つずつ追加して過学習の改善を測定する
   - `Dropout(p=0.5)` を各隠れ層に追加
   - `BatchNorm1d` を各隠れ層に追加
   - `Adam(..., weight_decay=1e-4)` で L2 正則化を適用
3. 正則化あり/なしの検証損失曲線を 1 枚の図にまとめる

---

## 提出チェックリスト

- [ ] `pytorch_intro.ipynb` の全セルを実行して出力を確認した
- [ ] 訓練/検証損失と精度の曲線をプロットできた
- [ ] `model.train()` と `model.eval()` の違いを説明できる
- [ ] `optimizer.zero_grad()` が必要な理由を説明できる
