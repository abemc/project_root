# ディープラーニング基礎ノート

## 1. ニューラルネットワークの構成要素

### 人工ニューロン

$$z = \mathbf{w}^T\mathbf{x} + b, \quad a = \sigma(z)$$

- $\mathbf{w}$: 重みベクトル
- $b$: バイアス
- $\sigma$: 活性化関数

### 活性化関数

| 関数 | 式 | 用途 |
|---|---|---|
| ReLU | $\max(0, x)$ | 隠れ層（最も一般的）|
| Sigmoid | $1/(1+e^{-x})$ | 二値分類の出力層 |
| Softmax | $e^{x_i}/\sum_j e^{x_j}$ | 多クラス分類の出力層 |
| Tanh | $(e^x - e^{-x})/(e^x + e^{-x})$ | RNN の隠れ層 |
| GELU | $x \cdot \Phi(x)$ | Transformer |

```python
import torch
import torch.nn.functional as F

x = torch.tensor([-2.0, -1.0, 0.0, 1.0, 2.0])
print("ReLU   :", F.relu(x))
print("Sigmoid:", torch.sigmoid(x))
print("Tanh   :", torch.tanh(x))
```

---

## 2. 損失関数

| タスク | 損失関数 | PyTorch |
|---|---|---|
| 回帰 | MSE | `nn.MSELoss()` |
| 二値分類 | Binary Cross-Entropy | `nn.BCEWithLogitsLoss()` |
| 多クラス分類 | Cross-Entropy | `nn.CrossEntropyLoss()` |

```python
import torch.nn as nn

# 多クラス分類（ロジット → ソフトマックス → クロスエントロピー）
criterion = nn.CrossEntropyLoss()
logits = torch.tensor([[2.0, 1.0, 0.1]])
labels = torch.tensor([0])                 # クラス 0 が正解
loss = criterion(logits, labels)
print(f"損失: {loss.item():.4f}")
```

---

## 3. PyTorch 入門

### テンソル操作

```python
import torch

# テンソルの作成
a = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
b = torch.zeros(2, 3)
c = torch.randn(3, 3)          # 標準正規分布

# 基本演算
print(a.shape)                  # torch.Size([2, 2])
print(a.T)                      # 転置
print(a @ a)                    # 行列積
print(a.sum(), a.mean())

# NumPy との変換
arr = a.numpy()                 # Tensor → NumPy
t   = torch.from_numpy(arr)    # NumPy → Tensor

# GPU への移動（利用可能な場合）
device = "cuda" if torch.cuda.is_available() else "cpu"
a = a.to(device)
```

### 自動微分（autograd）

```python
x = torch.tensor(3.0, requires_grad=True)
y = x**2 + 2*x + 1             # y = (x+1)^2

y.backward()                    # dy/dx を計算
print(x.grad)                   # dy/dx = 2x + 2 = 8.0
```

---

## 4. モデル定義

```python
import torch
import torch.nn as nn

class MLP(nn.Module):
    """多層パーセプトロン（Multilayer Perceptron）"""

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int,
                 dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

# モデルのインスタンス化と確認
model = MLP(input_dim=4, hidden_dim=64, output_dim=3)
print(model)
print(f"パラメータ数: {sum(p.numel() for p in model.parameters()):,}")

# ダミー入力でフォワードパスの確認
x = torch.randn(8, 4)          # バッチサイズ 8, 入力次元 4
out = model(x)
print(f"出力形状: {out.shape}") # (8, 3)
```

---

## 5. 訓練ループ

```python
import torch
import torch.nn as nn
import torch.optim as optim

def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    for X_batch, y_batch in loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        optimizer.zero_grad()       # 勾配をリセット
        outputs = model(X_batch)    # フォワードパス
        loss = criterion(outputs, y_batch)
        loss.backward()             # 誤差逆伝播
        optimizer.step()            # パラメータ更新
        total_loss += loss.item() * len(X_batch)
    return total_loss / len(loader.dataset)


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = correct = 0
    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            outputs = model(X_batch)
            total_loss += criterion(outputs, y_batch).item() * len(X_batch)
            preds = outputs.argmax(dim=1)
            correct += (preds == y_batch).sum().item()
    n = len(loader.dataset)
    return total_loss / n, correct / n
```

---

## 6. モデルの保存と読み込み

```python
# 保存（推奨: state_dict のみ保存）
torch.save(model.state_dict(), "model.pth")

# 読み込み
model_loaded = MLP(input_dim=4, hidden_dim=64, output_dim=3)
model_loaded.load_state_dict(torch.load("model.pth", map_location="cpu"))
model_loaded.eval()
```

---

## 7. CNN・RNN の概要

### CNN（畳み込みニューラルネット）

```python
class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),  # グレースケール入力
            nn.ReLU(),
            nn.MaxPool2d(2),                              # 28→14
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),                              # 14→7
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 7 * 7, 128),
            nn.ReLU(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))
```

---

## チェックポイント確認

- [ ] テンソルの作成・演算・GPU 移動ができる
- [ ] `requires_grad=True` で勾配を計算できる
- [ ] `nn.Module` を継承してモデルを定義できる
- [ ] 訓練ループを実装してモデルを学習させられる
- [ ] モデルを保存・読み込みできる
- [ ] ReLU / Sigmoid / Softmax の違いと使い分けを説明できる
