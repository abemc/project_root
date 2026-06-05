# 模範解答: 機械学習のための数学

## 演習 1 — ベクトルと行列の基本演算

```python
import numpy as np

# コサイン類似度
a = np.array([1, 2, 3], dtype=float)
b = np.array([4, 5, 6], dtype=float)
cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
print(f"コサイン類似度: {cos_sim:.4f}")  # 0.9746

# 行列演算
A = np.array([[2, 1, 0],
              [1, 3, 1],
              [0, 1, 2]], dtype=float)

det     = np.linalg.det(A)
A_inv   = np.linalg.inv(A)
eigvals, eigvecs = np.linalg.eig(A)

print(f"行列式: {det:.4f}")
print("逆行列:\n", A_inv)
print(f"固有値: {eigvals}")

# 検証
assert np.allclose(A @ A_inv, np.eye(3)), "単位行列になっていません"
print("A @ A_inv ≈ I: OK")
```

---

## 演習 2 — 正規分布とサンプリング

```python
import numpy as np

np.random.seed(0)

# N(0,1)
s1 = np.random.normal(0, 1, 10_000)
print(f"N(0,1) — 平均: {s1.mean():.4f}, 標準偏差: {s1.std():.4f}")

# N(5, 4)
mu, sigma = 5, 2
s2 = np.random.normal(mu, sigma, 10_000)
in_range = np.sum((s2 >= mu - sigma) & (s2 <= mu + sigma)) / len(s2) * 100
print(f"N(5,4) — 平均: {s2.mean():.4f}, 標準偏差: {s2.std():.4f}")
print(f"[mu-σ, mu+σ] に含まれる割合: {in_range:.1f}%")  # ≈ 68%

# ヒストグラム（コメントアウト: ノートブックで実行）
# import matplotlib.pyplot as plt
# plt.hist(s2, bins=50, edgecolor="k")
# plt.title("N(5, 4) のサンプル分布")
# plt.show()
```

---

## 演習 3 — 勾配降下法の実装

```python
import numpy as np

# 解析解: ∇f(x,y) = [2(x-3), 4(y+1)]
def f(v):
    return (v[0] - 3)**2 + 2 * (v[1] + 1)**2

def grad_f(v):
    return np.array([2 * (v[0] - 3), 4 * (v[1] + 1)])

# 数値勾配
def numerical_gradient(f, v, h=1e-5):
    grad = np.zeros_like(v, dtype=float)
    for i in range(len(v)):
        vp = v.copy(); vp[i] += h
        vm = v.copy(); vm[i] -= h
        grad[i] = (f(vp) - f(vm)) / (2 * h)
    return grad

v0 = np.array([0.0, 0.0])
print("数値勾配:", numerical_gradient(f, v0))   # [-6. 4.]
print("解析勾配:", grad_f(v0))                   # [-6.  4.]

# 勾配降下法
def gradient_descent(grad_fn, x_init, lr=0.01, n_iter=500):
    x = x_init.copy()
    for _ in range(n_iter):
        x -= lr * grad_fn(x)
    return x

for lr in [0.001, 0.01, 0.1, 0.5]:
    result = gradient_descent(grad_f, np.array([0.0, 0.0]), lr=lr)
    print(f"lr={lr:.3f} → x={result[0]:.4f}, y={result[1]:.4f}")
# lr=0.5 は収束しないか発散する可能性あり → 適切な学習率の重要性を体感
```

---

## 演習 4 — PCA 手実装

```python
import numpy as np

np.random.seed(42)
x = np.random.randn(100)
y = 0.8 * x + 0.2 * np.random.randn(100)
X = np.column_stack([x, y])

# 1. 標準化
X_std = (X - X.mean(axis=0)) / X.std(axis=0)

# 2. 共分散行列
cov = np.cov(X_std.T)             # shape: (2, 2)

# 3. 固有値・固有ベクトル
eigvals, eigvecs = np.linalg.eig(cov)

# 4. 固有値の大きい順に並び替え
idx      = np.argsort(eigvals)[::-1]
eigvals  = eigvals[idx]
eigvecs  = eigvecs[:, idx]

print("固有値:", eigvals)          # 第1主成分が大きい
print("第1主成分:", eigvecs[:, 0])

# 5. 射影
X_pca = X_std @ eigvecs

# sklearn との比較
from sklearn.decomposition import PCA
pca = PCA(n_components=2)
X_pca_sk = pca.fit_transform(X_std)
# 符号は異なる場合があるが絶対値は一致する
print("手実装と sklearn の差:", np.allclose(np.abs(X_pca), np.abs(X_pca_sk)))
```

---

## 演習 5 — クロスエントロピー損失と勾配

```python
import numpy as np

logits = np.array([2.0, 1.0, 0.5])
y_true = np.array([1, 0, 0], dtype=float)

# 1. ソフトマックス（数値安定化）
def softmax(z):
    z = z - np.max(z)           # オーバーフロー防止
    exp_z = np.exp(z)
    return exp_z / exp_z.sum()

y_pred = softmax(logits)
print("ソフトマックス出力:", y_pred)  # [0.659, 0.242, 0.099]

# 2. クロスエントロピー損失
def cross_entropy_loss(y_true, y_pred):
    return -np.sum(y_true * np.log(y_pred + 1e-10))

loss = cross_entropy_loss(y_true, y_pred)
print(f"損失: {loss:.4f}")  # ≈ 0.418

# 3. 解析勾配 ∂L/∂z = ŷ - y
grad_analytic = y_pred - y_true
print("解析勾配:", grad_analytic)

# 4. 数値勾配で確認
def loss_fn(z):
    return cross_entropy_loss(y_true, softmax(z))

h = 1e-5
grad_numeric = np.array([(loss_fn(logits + h * np.eye(3)[i]) -
                           loss_fn(logits - h * np.eye(3)[i])) / (2 * h)
                          for i in range(3)])
print("数値勾配:", grad_numeric)
print("一致:", np.allclose(grad_analytic, grad_numeric, atol=1e-4))
```
