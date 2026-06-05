# 演習: 機械学習 基礎

## 演習 1 — 線形回帰と特徴量エンジニアリング

**データ**: カリフォルニア住宅価格データセット（`sklearn.datasets.fetch_california_housing`）

**要件:**
1. データを読み込み、形状と基本統計量を確認する
2. 特徴量を `StandardScaler` で標準化する
3. `LinearRegression` で訓練・予測する
4. RMSE と R² を計算して表示する
5. **発展**: 多項式特徴量（`PolynomialFeatures(degree=2)`）を追加して性能比較する

```python
from sklearn.datasets import fetch_california_housing
housing = fetch_california_housing()
X, y = housing.data, housing.target
feature_names = housing.feature_names
```

---

## 演習 2 — 分類モデルの比較

**データ**: 乳がん診断データセット（`sklearn.datasets.load_breast_cancer`）

**要件:**
1. 以下の 4 つのモデルを比較する
   - `LogisticRegression`
   - `DecisionTreeClassifier`
   - `RandomForestClassifier`
   - `SVC`（サポートベクターマシン）
2. 各モデルに `StandardScaler` + `GridSearchCV` を組み合わせ、最適なハイパーパラメータを探索する
3. テストデータで Accuracy, Precision, Recall, F1 を計算してテーブル形式で表示する
4. 混同行列を可視化する（`seaborn.heatmap` または `matplotlib`）

---

## 演習 3 — 不均衡データへの対応

**目標**: クラス不均衡があるときの対処法を理解する。

```python
from sklearn.datasets import make_classification

X, y = make_classification(
    n_samples=1000,
    weights=[0.95, 0.05],   # 5% が少数クラス
    random_state=42,
    n_features=10,
)
```

**要件:**
1. クラス分布を確認する（`np.bincount(y)`）
2. 重み付けなしで `LogisticRegression` を訓練し、Accuracy と F1 を計算する
3. `class_weight="balanced"` を設定して再訓練し、F1 の変化を確認する
4. `SMOTE`（オーバーサンプリング）を使って再訓練する（`imbalanced-learn` が必要）
5. 3 つのアプローチの F1 スコアを比較してまとめる

---

## 演習 4 — パイプラインと交差検証

**目標**: `Pipeline` と `cross_val_score` を使って正しい評価フローを実装する。

**要件:**
1. Iris データセットを使う
2. 以下のパイプラインを構築する
   ```
   StandardScaler → PCA(n_components=2) → RandomForestClassifier
   ```
3. 5 分割交差検証で平均精度と標準偏差を計算する
4. `GridSearchCV` でランダムフォレストの `n_estimators` と `max_depth` を探索する
5. 最良モデルのテスト精度を報告する

---

## 演習 5 — 発展: 特徴量重要度とモデル解釈

**目標**: ランダムフォレストの特徴量重要度を分析する。

**データ**: カリフォルニア住宅価格（演習 1 と同じ）

**要件:**
1. `RandomForestRegressor` を訓練する
2. `feature_importances_` を棒グラフで可視化する
3. 上位 3 つの特徴量と目的変数の散布図を描く
4. **発展**: `permutation_importance` と `feature_importances_` の結果を比較する

---

## 提出チェックリスト

- [ ] `ml_basics.ipynb` の全セルを実行して出力を確認した
- [ ] Accuracy だけでなく Precision/Recall/F1 で評価する理由を説明できる
- [ ] 不均衡データに対処する 3 つの手法の違いを説明できる
- [ ] パイプラインを使う利点（データリーク防止）を説明できる
