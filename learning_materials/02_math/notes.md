# 機械学習のための数学ノート

## 1. 線形代数

### ベクトル

```python
import numpy as np

# 列ベクトル（形状: (3,) または (3,1)）
v = np.array([1, 2, 3])

# ノルム（大きさ）
norm = np.linalg.norm(v)                # L2 ノルム = √14

# 内積（ドット積）
u = np.array([4, 5, 6])
dot = np.dot(v, u)                      # 1*4 + 2*5 + 3*6 = 32

# コサイン類似度
cos_sim = dot / (np.linalg.norm(v) * np.linalg.norm(u))
```

### 行列

```python
A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

# 行列の積
C = A @ B                               # または np.dot(A, B)

# 転置
A_T = A.T

# 逆行列
A_inv = np.linalg.inv(A)

# 行列式
det = np.linalg.det(A)                  # -2.0

# 検証: A @ A_inv ≈ 単位行列
np.allclose(A @ A_inv, np.eye(2))       # True
```

### 固有値・固有ベクトル

**定義**: $A\mathbf{v} = \lambda\mathbf{v}$ を満たす $\lambda$（固有値）と $\mathbf{v}$（固有ベクトル）

```python
eigenvalues, eigenvectors = np.linalg.eig(A)
print("固有値:", eigenvalues)
print("固有ベクトル（列ごと）:\n", eigenvectors)

# 検証
for i in range(len(eigenvalues)):
    lam = eigenvalues[i]
    v = eigenvectors[:, i]
    assert np.allclose(A @ v, lam * v)
```

**機械学習での用途**: PCA（主成分分析）では共分散行列の固有ベクトルが主成分になる。

### 特異値分解 (SVD)

```python
U, S, Vt = np.linalg.svd(A)
# A ≈ U @ diag(S) @ Vt
A_reconstructed = U @ np.diag(S) @ Vt
```

---

## 2. 確率・統計

### 基本統計量

```python
data = np.array([2, 4, 4, 4, 5, 5, 7, 9])

mean     = np.mean(data)       # 期待値 E[X] = 5.0
variance = np.var(data)        # 分散 Var[X] = 4.0
std      = np.std(data)        # 標準偏差 σ = 2.0
median   = np.median(data)     # 中央値 = 4.5
```

### 主要な確率分布

| 分布 | 用途 | NumPy |
|---|---|---|
| 正規分布 $\mathcal{N}(\mu, \sigma^2)$ | 連続データ、誤差の仮定 | `np.random.normal(mu, sigma, n)` |
| ベルヌーイ分布 | 2 値の試行 | `np.random.binomial(1, p, n)` |
| 二項分布 | n 回試行での成功数 | `np.random.binomial(n, p, size)` |
| ポアソン分布 | 単位時間あたりの事象数 | `np.random.poisson(lam, n)` |
| 一様分布 | ランダムサンプリング | `np.random.uniform(low, high, n)` |

```python
# 正規分布からサンプリングして可視化
samples = np.random.normal(loc=0, scale=1, size=1000)
print(f"平均: {samples.mean():.3f}, 標準偏差: {samples.std():.3f}")
```

### ベイズの定理

$$P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}$$

- $P(A)$: 事前確率 (Prior)
- $P(B|A)$: 尤度 (Likelihood)
- $P(A|B)$: 事後確率 (Posterior)

---

## 3. 微分と最適化

### 偏微分と勾配

関数 $f(\mathbf{x})$ の勾配 $\nabla f$ は各変数に関する偏微分を並べたベクトル。

$$\nabla f = \left(\frac{\partial f}{\partial x_1}, \frac{\partial f}{\partial x_2}, \ldots, \frac{\partial f}{\partial x_n}\right)$$

```python
# 数値微分（前進差分）
def numerical_gradient(f, x, h=1e-5):
    grad = np.zeros_like(x, dtype=float)
    for i in range(len(x)):
        x_fwd = x.copy(); x_fwd[i] += h
        x_bwd = x.copy(); x_bwd[i] -= h
        grad[i] = (f(x_fwd) - f(x_bwd)) / (2 * h)
    return grad

# 例: f(x, y) = x^2 + 2y^2
f = lambda v: v[0]**2 + 2 * v[1]**2
grad = numerical_gradient(f, np.array([3.0, 4.0]))
print(grad)  # [6. 16.]  ← 解析解 [2x, 4y] = [6, 16]
```

### 勾配降下法

$$\mathbf{x}_{t+1} = \mathbf{x}_t - \eta \nabla f(\mathbf{x}_t)$$

```python
def gradient_descent(f, grad_f, x_init, lr=0.01, n_iter=100):
    x = x_init.copy().astype(float)
    history = [x.copy()]
    for _ in range(n_iter):
        x -= lr * grad_f(x)
        history.append(x.copy())
    return x, history

# 例: f(x) = x^2 の最小化
f      = lambda x: x[0]**2
grad_f = lambda x: np.array([2 * x[0]])

x_min, history = gradient_descent(f, grad_f, np.array([5.0]), lr=0.1)
print(f"最小点: x = {x_min[0]:.6f}")  # ≈ 0
```

### 連鎖律（Chain Rule）

ニューラルネットワークの誤差逆伝播（バックプロパゲーション）の基礎。

$$\frac{\partial L}{\partial x} = \frac{\partial L}{\partial y} \cdot \frac{\partial y}{\partial x}$$

---

## 4. 情報理論の基礎

### エントロピー

$$H(X) = -\sum_i p_i \log_2 p_i$$

```python
def entropy(probs):
    probs = np.array(probs)
    return -np.sum(probs * np.log2(probs + 1e-10))

# コイン投げ（公平: 最大エントロピー）
print(entropy([0.5, 0.5]))   # 1.0 bit
# 偏ったコイン（低エントロピー）
print(entropy([0.9, 0.1]))   # ≈ 0.47 bit
```

### クロスエントロピー損失

分類問題の損失関数として広く使われる。

$$L = -\sum_i y_i \log(\hat{y}_i)$$

```python
def cross_entropy_loss(y_true, y_pred):
    return -np.sum(y_true * np.log(y_pred + 1e-10))
```

---

## チェックポイント確認

- [ ] NumPy で行列の積・転置・逆行列を計算できる
- [ ] 固有値・固有ベクトルを計算して意味を説明できる
- [ ] 正規分布・二項分布からサンプリングできる
- [ ] 数値微分を実装できる
- [ ] 勾配降下法を実装してシンプルな関数を最小化できる
