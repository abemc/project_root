# 模範解答: 機械学習 基礎

## 演習 1 — 線形回帰と特徴量エンジニアリング

```python
import numpy as np
from sklearn.datasets import fetch_california_housing
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, r2_score

housing = fetch_california_housing()
X, y = housing.data, housing.target

print(f"データ形状: {X.shape}")
print(f"目的変数: 平均 {y.mean():.2f}, 最大 {y.max():.2f}, 最小 {y.min():.2f}")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 線形回帰
pipe_lr = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
pipe_lr.fit(X_train, y_train)
y_pred = pipe_lr.predict(X_test)
print(f"\n線形回帰 RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
print(f"線形回帰 R²  : {r2_score(y_test, y_pred):.4f}")

# 多項式特徴量
pipe_poly = Pipeline([
    ("scaler", StandardScaler()),
    ("poly", PolynomialFeatures(degree=2, include_bias=False)),
    ("model", LinearRegression())
])
pipe_poly.fit(X_train, y_train)
y_pred_poly = pipe_poly.predict(X_test)
print(f"\n多項式回帰 RMSE: {np.sqrt(mean_squared_error(y_test, y_pred_poly)):.4f}")
print(f"多項式回帰 R²  : {r2_score(y_test, y_pred_poly):.4f}")
```

---

## 演習 2 — 分類モデルの比較

```python
import pandas as pd
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (accuracy_score, precision_score,
                              recall_score, f1_score)

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42)

models_params = {
    "LogisticRegression": (
        LogisticRegression(max_iter=1000),
        {"model__C": [0.1, 1, 10]}
    ),
    "DecisionTree": (
        DecisionTreeClassifier(),
        {"model__max_depth": [3, 5, 10, None]}
    ),
    "RandomForest": (
        RandomForestClassifier(random_state=42),
        {"model__n_estimators": [50, 100], "model__max_depth": [5, None]}
    ),
    "SVC": (
        SVC(),
        {"model__C": [0.1, 1, 10], "model__kernel": ["rbf", "linear"]}
    ),
}

results = []
for name, (clf, params) in models_params.items():
    pipe = Pipeline([("scaler", StandardScaler()), ("model", clf)])
    gs = GridSearchCV(pipe, params, cv=5, scoring="f1")
    gs.fit(X_train, y_train)
    y_pred = gs.predict(X_test)
    results.append({
        "Model": name,
        "Accuracy":  f"{accuracy_score(y_test, y_pred):.4f}",
        "Precision": f"{precision_score(y_test, y_pred):.4f}",
        "Recall":    f"{recall_score(y_test, y_pred):.4f}",
        "F1":        f"{f1_score(y_test, y_pred):.4f}",
    })

print(pd.DataFrame(results).to_string(index=False))
```

---

## 演習 3 — 不均衡データへの対応

```python
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, classification_report
import numpy as np

X, y = make_classification(n_samples=1000, weights=[0.95, 0.05],
                            random_state=42, n_features=10)
print("クラス分布:", np.bincount(y))  # [950, 50]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 1. 重み付けなし
lr_plain = LogisticRegression(max_iter=1000)
lr_plain.fit(X_train, y_train)
f1_plain = f1_score(y_test, lr_plain.predict(X_test))

# 2. class_weight="balanced"
lr_balanced = LogisticRegression(max_iter=1000, class_weight="balanced")
lr_balanced.fit(X_train, y_train)
f1_balanced = f1_score(y_test, lr_balanced.predict(X_test))

print(f"\n重み付けなし F1: {f1_plain:.4f}")
print(f"balanced F1    : {f1_balanced:.4f}")

# 3. SMOTE（imbalanced-learn が必要: pip install imbalanced-learn）
try:
    from imblearn.over_sampling import SMOTE
    sm = SMOTE(random_state=42)
    X_sm, y_sm = sm.fit_resample(X_train, y_train)
    lr_smote = LogisticRegression(max_iter=1000)
    lr_smote.fit(X_sm, y_sm)
    f1_smote = f1_score(y_test, lr_smote.predict(X_test))
    print(f"SMOTE F1       : {f1_smote:.4f}")
except ImportError:
    print("imbalanced-learn が未インストールです: pip install imbalanced-learn")
```

---

## 演習 4 — パイプラインと交差検証

```python
from sklearn.datasets import load_iris
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

iris = load_iris()
X, y = iris.data, iris.target
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("pca",    PCA(n_components=2)),
    ("model",  RandomForestClassifier(random_state=42)),
])

# 交差検証
scores = cross_val_score(pipe, X_train, y_train, cv=5, scoring="accuracy")
print(f"CV 平均精度: {scores.mean():.4f} ± {scores.std():.4f}")

# グリッドサーチ
params = {
    "model__n_estimators": [50, 100, 200],
    "model__max_depth": [None, 3, 5],
}
gs = GridSearchCV(pipe, params, cv=5, scoring="accuracy")
gs.fit(X_train, y_train)
print("最良パラメータ:", gs.best_params_)
print(f"テスト精度: {gs.score(X_test, y_test):.4f}")
```

---

## 演習 5 — 発展: 特徴量重要度とモデル解釈

```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
import numpy as np

housing = fetch_california_housing()
X_train, X_test, y_train, y_test = train_test_split(
    housing.data, housing.target, test_size=0.2, random_state=42)

rf = RandomForestRegressor(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)

# 組み込み重要度
imp_builtin = rf.feature_importances_
print("=== 組み込み重要度 ===")
for name, imp in sorted(zip(housing.feature_names, imp_builtin),
                         key=lambda x: -x[1]):
    print(f"  {name:20s}: {imp:.4f}")

# Permutation Importance
perm = permutation_importance(rf, X_test, y_test, n_repeats=10, random_state=42)
print("\n=== Permutation Importance ===")
for name, imp in sorted(zip(housing.feature_names, perm.importances_mean),
                         key=lambda x: -x[1]):
    print(f"  {name:20s}: {imp:.4f}")
```
