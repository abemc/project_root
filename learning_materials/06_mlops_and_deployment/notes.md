# MLOps とデプロイ ノート

## 1. モデルの保存とバージョン管理

### scikit-learn モデルの保存

```python
import joblib
from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# 保存
joblib.dump(model, "model_v1.0.pkl")

# 読み込み
model_loaded = joblib.load("model_v1.0.pkl")
```

### PyTorch モデルの保存

```python
import torch

# 推奨: state_dict のみ保存
torch.save(model.state_dict(), "model.pth")

# チェックポイント（再開可能な形式）
torch.save({
    "epoch": epoch,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "loss": loss,
}, "checkpoint.pth")

# 読み込み
checkpoint = torch.load("checkpoint.pth", map_location="cpu")
model.load_state_dict(checkpoint["model_state_dict"])
optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
epoch = checkpoint["epoch"]
```

### MLflow でのモデル管理

```python
import mlflow
import mlflow.sklearn

with mlflow.start_run():
    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("max_depth", 5)
    mlflow.log_metric("accuracy", accuracy)
    mlflow.sklearn.log_model(model, "model")

# モデルの読み込み
loaded = mlflow.sklearn.load_model("runs:/<run_id>/model")
```

---

## 2. FastAPI で推論 API を作る

### 基本的な API サーバー

```python
# inference_api.py 参照
from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import numpy as np

app = FastAPI()
model = joblib.load("model.pkl")

class PredictRequest(BaseModel):
    features: list[float]

class PredictResponse(BaseModel):
    prediction: int
    probability: list[float]

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    X = np.array(req.features).reshape(1, -1)
    pred = int(model.predict(X)[0])
    prob = model.predict_proba(X)[0].tolist()
    return PredictResponse(prediction=pred, probability=prob)
```

実行:
```bash
uvicorn inference_api:app --reload --port 8000
```

テスト:
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
```

---

## 3. Docker でコンテナ化

### Dockerfile の例

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY . .

# ポートを公開
EXPOSE 8000

# サーバーを起動
CMD ["uvicorn", "inference_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.1
scikit-learn==1.5.0
numpy==1.26.4
joblib==1.4.2
pydantic==2.7.1
```

### Docker コマンド

```bash
# イメージのビルド
docker build -t ml-api:latest .

# コンテナの起動
docker run -p 8000:8000 ml-api:latest

# バックグラウンドで起動
docker run -d -p 8000:8000 --name ml-api ml-api:latest

# ログの確認
docker logs ml-api

# コンテナの停止・削除
docker stop ml-api && docker rm ml-api
```

---

## 4. モニタリングとロギング

### 予測ログの記録

```python
import logging
import json
from datetime import datetime

pred_logger = logging.getLogger("predictions")
pred_logger.setLevel(logging.INFO)
handler = logging.FileHandler("predictions.log", encoding="utf-8")
pred_logger.addHandler(handler)

def log_prediction(request_id: str, features: list, prediction: int,
                   probability: list, latency_ms: float):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "features": features,
        "prediction": prediction,
        "max_probability": max(probability),
        "latency_ms": latency_ms,
    }
    pred_logger.info(json.dumps(record, ensure_ascii=False))
```

### データドリフトの検出

```python
from scipy.stats import ks_2samp

def detect_drift(reference: np.ndarray, current: np.ndarray,
                 threshold: float = 0.05) -> bool:
    """KS 検定でデータドリフトを検出する。"""
    _, p_value = ks_2samp(reference, current)
    return p_value < threshold  # True なら分布が有意に変化

# 特徴量ごとにドリフトを確認
for i, feature_name in enumerate(feature_names):
    is_drift = detect_drift(X_train[:, i], X_prod[:, i])
    if is_drift:
        print(f"⚠️ ドリフト検出: {feature_name}")
```

---

## 5. バッチ推論とストリーミング推論

### バッチ推論

```python
import pandas as pd

def batch_predict(model, input_csv: str, output_csv: str,
                  batch_size: int = 1000):
    """大規模データをバッチで推論する。"""
    chunks = pd.read_csv(input_csv, chunksize=batch_size)
    results = []
    for chunk in chunks:
        preds = model.predict(chunk.values)
        chunk["prediction"] = preds
        results.append(chunk)
    pd.concat(results).to_csv(output_csv, index=False)
    print(f"推論完了: {output_csv}")
```

---

## チェックポイント確認

- [ ] モデルを joblib / torch.save で保存・読み込みできる
- [ ] FastAPI で `/predict` エンドポイントを実装できる
- [ ] Dockerfile を書いてコンテナをビルド・実行できる
- [ ] 予測ログを構造化された形式で記録できる
- [ ] データドリフトを KS 検定で検出できる
