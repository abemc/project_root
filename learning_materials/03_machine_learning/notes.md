# 機械学習 基礎ノート

## 1. 教師あり学習の枠組み

機械学習の目標: 入力 $\mathbf{x}$ から出力 $y$ を予測するモデル $f$ を学習する。

$$\hat{y} = f(\mathbf{x}; \theta)$$

- **訓練データ**: $(x_i, y_i)_{i=1}^{N}$
- **損失関数**: $L(\theta) = \frac{1}{N}\sum_i \ell(y_i, \hat{y}_i)$（予測と正解のズレ）
- **最適化**: $\theta^* = \arg\min_\theta L(\theta)$

---

## 2. 線形回帰

**目標**: 連続値の予測

$$\hat{y} = \mathbf{w}^T \mathbf{x} + b$$

- 損失関数: MSE（平均二乗誤差）
- 閉形式解: $\mathbf{w}^* = (\mathbf{X}^T\mathbf{X})^{-1}\mathbf{X}^T\mathbf{y}$

```python
from sklearn.linear_model import LinearRegression
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import numpy as np

X, y = make_regression(n_samples=200, n_features=3, noise=10, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = LinearRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"RMSE: {rmse:.3f}")
print(f"係数: {model.coef_}")
```

---

## 3. ロジスティック回帰

**目標**: 2値分類（または多クラス分類）

$$P(y=1|\mathbf{x}) = \sigma(\mathbf{w}^T\mathbf{x} + b) = \frac{1}{1 + e^{-z}}$$

- 損失関数: バイナリクロスエントロピー
- 出力は確率（0〜1）

```python
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import load_breast_cancer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42)

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000))
])
pipe.fit(X_train, y_train)
print(classification_report(y_test, pipe.predict(X_test)))
```

---

## 4. 決定木とランダムフォレスト

### 決定木

- 特徴量のしきい値で分岐を繰り返す
- 分岐の基準: **ジニ不純度** または **情報エントロピー**
- 過学習しやすい → 剪定（`max_depth` など）が重要

$$\text{Gini} = 1 - \sum_k p_k^2$$

### ランダムフォレスト

- 複数の決定木の予測を集約（バギング）
- 各木で特徴量をランダムサブセットから選択
- 過学習を抑えつつ性能が高い

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score

iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42)

rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)
acc = accuracy_score(y_test, rf.predict(X_test))
print(f"精度: {acc:.4f}")

# 特徴量重要度
for name, imp in zip(iris.feature_names, rf.feature_importances_):
    print(f"  {name}: {imp:.4f}")
```

---

## 5. 特徴量エンジニアリング

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder

# 数値特徴量の正規化
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# カテゴリ変数のエンコーディング
# Label Encoding（順序あり）
le = LabelEncoder()
y_encoded = le.fit_transform(["cat", "dog", "cat", "bird"])

# One-Hot Encoding（順序なし）
from sklearn.preprocessing import OneHotEncoder
ohe = OneHotEncoder(sparse_output=False)
X_encoded = ohe.fit_transform([["cat"], ["dog"], ["bird"]])
```

### 欠損値の処理

```python
from sklearn.impute import SimpleImputer

# 平均値で補完
imputer = SimpleImputer(strategy="mean")
X_imputed = imputer.fit_transform(X)

# 中央値で補完（外れ値に強い）
imputer_median = SimpleImputer(strategy="median")
```

---

## 6. モデル評価

### 分類の評価指標

| 指標 | 定義 | 用途 |
|---|---|---|
| Accuracy | 正解率 | クラスバランスが均等なとき |
| Precision | TP / (TP + FP) | 偽陽性を減らしたいとき |
| Recall | TP / (TP + FN) | 偽陰性を減らしたいとき |
| F1 | 2 × P × R / (P + R) | バランスよく評価するとき |
| ROC-AUC | ROC 曲線下面積 | 閾値に依存しない性能評価 |

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)

# 各指標の計算
print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
print(f"Precision: {precision_score(y_test, y_pred):.4f}")
print(f"Recall   : {recall_score(y_test, y_pred):.4f}")
print(f"F1       : {f1_score(y_test, y_pred):.4f}")

# 混同行列
cm = confusion_matrix(y_test, y_pred)
print("混同行列:\n", cm)
```

### 回帰の評価指標

```python
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

print(f"MSE : {mean_squared_error(y_test, y_pred):.4f}")
print(f"MAE : {mean_absolute_error(y_test, y_pred):.4f}")
print(f"R²  : {r2_score(y_test, y_pred):.4f}")
```

---

## 7. 交差検証とハイパーパラメータ探索

```python
from sklearn.model_selection import cross_val_score, GridSearchCV

# k-Fold 交差検証
scores = cross_val_score(rf, X, y, cv=5, scoring="accuracy")
print(f"CV 精度: {scores.mean():.4f} ± {scores.std():.4f}")

# グリッドサーチ
param_grid = {
    "n_estimators": [50, 100, 200],
    "max_depth": [None, 5, 10],
}
gs = GridSearchCV(RandomForestClassifier(random_state=42),
                  param_grid, cv=5, scoring="accuracy", n_jobs=-1)
gs.fit(X_train, y_train)
print("最良パラメータ:", gs.best_params_)
print(f"最良スコア: {gs.best_score_:.4f}")
```

---

## チェックポイント確認

- [ ] 線形回帰・ロジスティック回帰を scikit-learn で実装できる
- [ ] Precision と Recall のトレードオフを説明できる
- [ ] 特徴量の標準化が必要な理由を説明できる
- [ ] 交差検証の目的と実装方法を理解している
- [ ] グリッドサーチでハイパーパラメータを最適化できる
