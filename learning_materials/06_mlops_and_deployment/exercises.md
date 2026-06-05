# 演習: MLOps とデプロイ

## 演習 1 — モデルの保存と読み込み

**目標**: 訓練済みモデルを保存・読み込みし、同じ予測結果が得られることを確認する。

**要件:**
1. `RandomForestClassifier` を Iris データで訓練する
2. `joblib.dump` でモデルを保存し、`joblib.load` で読み込む
3. 元のモデルと読み込んだモデルで同じ予測が得られることを `np.allclose` で確認する
4. モデルのメタデータ（訓練日時、精度、ハイパーパラメータ）を JSON ファイルとして一緒に保存する

```python
metadata = {
    "trained_at": "...",       # datetime.utcnow().isoformat()
    "accuracy": ...,
    "params": model.get_params(),
    "sklearn_version": ...,    # sklearn.__version__
}
```

---

## 演習 2 — FastAPI 推論 API の実装

**目標**: `inference_api.py`（同フォルダー）を動かして API をテストする。

**要件:**
1. Iris データで `RandomForestClassifier` を訓練し、`iris_model.pkl` として保存する
2. `inference_api.py` のコードを参考に、Iris 分類用 API を実装する（またはそのまま使う）
3. サーバーを起動する:
   ```bash
   uvicorn inference_api:app --reload
   ```
4. 以下のエンドポイントをテストする:
   - `GET /health` — ヘルスチェック
   - `POST /predict` — 単一サンプルの予測
5. `requests` ライブラリで Python からも呼び出す:

```python
import requests
resp = requests.post(
    "http://localhost:8000/predict",
    json={"features": [5.1, 3.5, 1.4, 0.2]}
)
print(resp.json())
```

---

## 演習 3 — Dockerfile の作成とコンテナ化

**目標**: 演習 2 の API を Docker コンテナとして実行する。

**要件:**
1. `Dockerfile` を作成する（`notes.md` の例を参考に）
2. `requirements.txt` を作成する
3. イメージをビルドする:
   ```bash
   docker build -t iris-api:latest .
   ```
4. コンテナを起動してテストする:
   ```bash
   docker run -p 8000:8000 iris-api:latest
   ```
5. コンテナ内のログを確認する

> **注意**: Docker がインストールされていない場合はスキップ可。  
> 代わりに `requirements.txt` と `Dockerfile` の内容を手で確認する。

---

## 演習 4 — バッチ推論スクリプトの実装

**目標**: 大量データを CSV で受け取り、予測結果を CSV で出力するスクリプトを実装する。

```bash
python batch_predict.py --input data.csv --output predictions.csv --model iris_model.pkl
```

**要件:**
1. `argparse` でコマンドライン引数を受け取る
2. CSV を `chunksize=500` で読み込む
3. 各チャンクで推論し、`prediction` 列を追加して出力 CSV に書き込む
4. 処理したサンプル数と所要時間をログに出力する
5. エラーが発生したチャンクはスキップしてログに記録する

---

## 演習 5 — モニタリング: データドリフト検出（発展）

**目標**: 本番データが訓練データから乖離していないかを統計的に検出する。

```python
from sklearn.datasets import load_iris
import numpy as np

iris = load_iris()
X_train = iris.data[:100]   # 参照分布（訓練データ）

# ドリフトを人工的に発生させた本番データ
np.random.seed(42)
X_prod = iris.data[100:] + np.random.normal(loc=1.5, scale=0.5, size=iris.data[100:].shape)
```

**要件:**
1. KS 検定（`scipy.stats.ks_2samp`）で特徴量ごとにドリフトを検出する
2. ドリフトが検出された特徴量と p 値を表示する
3. 各特徴量の参照分布と本番分布を箱ひげ図で比較する
4. **発展**: `psi` (Population Stability Index) を計算してドリフトの強度を数値化する

---

## 提出チェックリスト

- [ ] モデルを joblib で保存・読み込みできた
- [ ] FastAPI の `/predict` エンドポイントが正常にレスポンスを返した
- [ ] `requests` で API を呼び出せた
- [ ] バッチ推論スクリプトが動作した
