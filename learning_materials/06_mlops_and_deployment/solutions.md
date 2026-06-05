# MLOps 模範解答

## 演習 1 — モデルの保存と読み込み

```python
import joblib
import json
import numpy as np
import sklearn
from datetime import datetime
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
acc = accuracy_score(y_test, model.predict(X_test))

# モデルを保存
joblib.dump(model, "iris_model.pkl")

# メタデータを保存
metadata = {
    "trained_at": datetime.utcnow().isoformat(),
    "accuracy": round(float(acc), 4),
    "params": model.get_params(),
    "sklearn_version": sklearn.__version__,
}
with open("model_metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"精度: {acc:.4f}")
print("保存完了: iris_model.pkl, model_metadata.json")

# 読み込みと検証
model_loaded = joblib.load("iris_model.pkl")
preds_orig   = model.predict(X_test)
preds_loaded = model_loaded.predict(X_test)
assert np.allclose(preds_orig, preds_loaded), "予測結果が一致しません"
print("元のモデルと読み込んだモデルの予測が一致: OK")
```

---

## 演習 2 — FastAPI 推論 API のテスト

```python
# モデルを作成・保存するスクリプト
import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier

iris = load_iris()
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(iris.data, iris.target)
joblib.dump({"model": model, "target_names": iris.target_names.tolist()},
            "iris_model.pkl")
print("iris_model.pkl を作成しました")
```

```bash
# サーバー起動
uvicorn inference_api:app --reload --port 8000

# ヘルスチェック
curl http://localhost:8000/health

# 予測リクエスト
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
```

```python
# Python からの呼び出し
import requests

resp = requests.post(
    "http://localhost:8000/predict",
    json={"features": [5.1, 3.5, 1.4, 0.2]},
    timeout=5,
)
print(resp.json())
# {'request_id': '...', 'prediction': 0, 'class_name': 'setosa', ...}
```

---

## 演習 4 — バッチ推論スクリプト

```python
# batch_predict.py
import argparse
import logging
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("batch_predict")


def batch_predict(input_path: str, output_path: str,
                  model_path: str, chunk_size: int = 500):
    artifact = joblib.load(model_path)
    model = artifact["model"] if isinstance(artifact, dict) else artifact

    total = processed = errors = 0
    t0 = time.perf_counter()

    chunks = []
    for i, chunk in enumerate(pd.read_csv(input_path, chunksize=chunk_size)):
        try:
            preds = model.predict(chunk.values)
            chunk["prediction"] = preds
            chunks.append(chunk)
            processed += len(chunk)
        except Exception as e:
            logger.error("チャンク %d のエラーをスキップ: %s", i, e)
            errors += len(chunk)
        total += len(chunk)

    pd.concat(chunks).to_csv(output_path, index=False, encoding="utf-8")
    elapsed = time.perf_counter() - t0
    logger.info("完了: 処理 %d / エラー %d / 合計 %d サンプル, %.2f秒",
                processed, errors, total, elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model",  default="iris_model.pkl")
    args = parser.parse_args()
    batch_predict(args.input, args.output, args.model)
```

---

## 演習 5 — データドリフト検出

```python
import numpy as np
from scipy.stats import ks_2samp
from sklearn.datasets import load_iris

iris = load_iris()
X_train = iris.data[:100]
np.random.seed(42)
X_prod = iris.data[100:] + np.random.normal(loc=1.5, scale=0.5,
                                              size=iris.data[100:].shape)

print("=== KS 検定によるドリフト検出 ===")
for i, name in enumerate(iris.feature_names):
    stat, p = ks_2samp(X_train[:, i], X_prod[:, i])
    status = "⚠️ ドリフト検出" if p < 0.05 else "✅ 正常"
    print(f"  {name:30s}: stat={stat:.3f}, p={p:.4f}  {status}")


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index を計算する（PSI > 0.2 は大きな変化）。"""
    breaks = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breaks[0] -= 1e-10
    breaks[-1] += 1e-10
    exp_pct = np.histogram(expected, bins=breaks)[0] / len(expected)
    act_pct = np.histogram(actual,   bins=breaks)[0] / len(actual)
    exp_pct = np.where(exp_pct == 0, 1e-10, exp_pct)
    act_pct = np.where(act_pct == 0, 1e-10, act_pct)
    return np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))

print("\n=== PSI ===")
for i, name in enumerate(iris.feature_names):
    p = psi(X_train[:, i], X_prod[:, i])
    level = "🔴 大" if p > 0.2 else "🟡 中" if p > 0.1 else "🟢 小"
    print(f"  {name:30s}: PSI={p:.4f}  {level}")
```
