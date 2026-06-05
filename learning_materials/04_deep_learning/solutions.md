# 模範解答: ディープラーニング 基礎

## 演習 1 — テンソル操作と自動微分

```python
import torch

# 行列積
torch.manual_seed(0)
A = torch.randn(3, 4)
B = torch.randn(4, 2)
C = A @ B
print(f"A @ B の形状: {C.shape}")  # (3, 2)

# f(x) = x^3 - 2x^2 + x の勾配
x = torch.tensor(2.0, requires_grad=True)
f = x**3 - 2*x**2 + x
f.backward()
print(f"df/dx at x=2: {x.grad.item()}")  # 解析解 = 3*4 - 4*2 + 1 = 5

# MSE 損失の勾配
torch.manual_seed(42)
X = torch.randn(100, 3)
w_true = torch.tensor([1.0, -2.0, 0.5])
y = X @ w_true + torch.randn(100) * 0.1

w = torch.zeros(3, requires_grad=True)
y_pred = X @ w
L = ((y - y_pred)**2).mean()
L.backward()
print(f"損失: {L.item():.4f}")
print(f"勾配 w.grad: {w.grad}")
```

---

## 演習 2 — MLP で Iris 分類

```python
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from sklearn.datasets import load_iris
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
import numpy as np

# データセット
class IrisDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

iris = load_iris()
scaler = StandardScaler()
X_scaled = scaler.fit_transform(iris.data)

dataset = IrisDataset(X_scaled, iris.target)
n_train = int(0.8 * len(dataset))
train_ds, val_ds = random_split(dataset, [n_train, len(dataset) - n_train])
train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
val_loader   = DataLoader(val_ds,   batch_size=16)

# モデル
class IrisMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 32), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 3),
        )
    def forward(self, x):
        return self.net(x)

model = IrisMLP()
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

train_losses, val_accs = [], []
for epoch in range(100):
    model.train()
    epoch_loss = 0
    for X_b, y_b in train_loader:
        optimizer.zero_grad()
        loss = criterion(model(X_b), y_b)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item() * len(X_b)
    train_losses.append(epoch_loss / len(train_ds))

    model.eval()
    correct = 0
    with torch.no_grad():
        for X_b, y_b in val_loader:
            correct += (model(X_b).argmax(1) == y_b).sum().item()
    val_accs.append(correct / len(val_ds))

print(f"最終訓練損失: {train_losses[-1]:.4f}")
print(f"最終検証精度: {val_accs[-1]:.4f}")

# 詳細レポート
model.eval()
all_preds = []
with torch.no_grad():
    for X_b, _ in val_loader:
        all_preds.extend(model(X_b).argmax(1).numpy())
print(classification_report(
    [val_ds[i][1].item() for i in range(len(val_ds))],
    all_preds, target_names=iris.target_names))
```

---

## 演習 3 — 簡易 CNN で FashionMNIST 分類

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

transform = transforms.Compose([transforms.ToTensor(),
                                 transforms.Normalize((0.5,), (0.5,))])
train_ds = datasets.FashionMNIST("./data", train=True, download=True, transform=transform)
test_ds  = datasets.FashionMNIST("./data", train=False, download=True, transform=transform)
train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
test_loader  = DataLoader(test_ds,  batch_size=64)

class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64*7*7, 128), nn.ReLU(),
            nn.Linear(128, 10),
        )
    def forward(self, x):
        return self.classifier(self.features(x))

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SimpleCNN().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

for epoch in range(5):
    model.train()
    for X, y in train_loader:
        X, y = X.to(device), y.to(device)
        optimizer.zero_grad()
        criterion(model(X), y).backward()
        optimizer.step()

    model.eval()
    correct = total = 0
    with torch.no_grad():
        for X, y in test_loader:
            X, y = X.to(device), y.to(device)
            correct += (model(X).argmax(1) == y).sum().item()
            total += len(y)
    print(f"Epoch {epoch+1}: テスト精度 = {correct/total:.4f}")
```

---

## 演習 4 — 学習率スケジューラの比較（例: Cosine Annealing）

```python
from torch.optim.lr_scheduler import CosineAnnealingLR

model = IrisMLP()
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
scheduler = CosineAnnealingLR(optimizer, T_max=100)

for epoch in range(100):
    # 訓練ループ（省略）
    ...
    scheduler.step()
    if (epoch+1) % 20 == 0:
        print(f"Epoch {epoch+1}: LR = {optimizer.param_groups[0]['lr']:.6f}")
```

---

## 演習 5 — 正則化テクニックの比較

```python
# BatchNorm + Dropout あり
class RegularizedMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(128, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(64, 3),
        )
    def forward(self, x):
        return self.net(x)

# Weight Decay (L2 正則化)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
```
