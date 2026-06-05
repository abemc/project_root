"""
inference_api.py — FastAPI を使った Iris 分類推論 API

使い方:
    # 1. モデルを事前に作成・保存しておく
    python -c "
    from sklearn.datasets import load_iris
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    iris = load_iris()
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(iris.data, iris.target)
    joblib.dump({'model': model, 'target_names': iris.target_names.tolist()}, 'iris_model.pkl')
    print('モデルを保存しました: iris_model.pkl')
    "

    # 2. サーバーを起動する
    uvicorn inference_api:app --reload --port 8000

    # 3. エンドポイントをテストする
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/predict \\
         -H "Content-Type: application/json" \\
         -d '{"features": [5.1, 3.5, 1.4, 0.2]}'

依存:
    pip install fastapi uvicorn scikit-learn joblib pydantic numpy
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

# ────────────────────────────────────────────
# ロガー設定
# ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inference_api")

# ────────────────────────────────────────────
# アプリ & モデルのロード
# ────────────────────────────────────────────
app = FastAPI(
    title="Iris 分類 API",
    description="RandomForestClassifier で Iris を 3 クラス分類します。",
    version="1.0.0",
)

MODEL_PATH = Path("iris_model.pkl")
_artifact: dict = {}


@app.on_event("startup")
def load_model() -> None:
    if not MODEL_PATH.exists():
        logger.warning("モデルファイルが見つかりません: %s", MODEL_PATH)
        return
    _artifact.update(joblib.load(MODEL_PATH))
    logger.info("モデルをロードしました: %s", MODEL_PATH)


# ────────────────────────────────────────────
# スキーマ定義
# ────────────────────────────────────────────
class PredictRequest(BaseModel):
    features: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Iris の 4 特徴量: [sepal_length, sepal_width, petal_length, petal_width]",
        examples=[[5.1, 3.5, 1.4, 0.2]],
    )

    @field_validator("features")
    @classmethod
    def check_positive(cls, v: list[float]) -> list[float]:
        if any(f < 0 for f in v):
            raise ValueError("特徴量はすべて非負の値である必要があります。")
        return v


class PredictResponse(BaseModel):
    request_id: str
    prediction: int
    class_name: str
    probability: list[float]
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


# ────────────────────────────────────────────
# エンドポイント
# ────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["utility"])
def health_check() -> HealthResponse:
    """サーバーとモデルの状態を確認します。"""
    return HealthResponse(
        status="ok",
        model_loaded="model" in _artifact,
    )


@app.post("/predict", response_model=PredictResponse, tags=["inference"])
def predict(req: PredictRequest) -> PredictResponse:
    """単一サンプルの Iris クラスを予測します。"""
    if "model" not in _artifact:
        raise HTTPException(status_code=503, detail="モデルがロードされていません。")

    request_id = str(uuid.uuid4())
    model = _artifact["model"]
    target_names: list[str] = _artifact.get(
        "target_names", ["setosa", "versicolor", "virginica"]
    )

    t0 = time.perf_counter()
    X = np.array(req.features, dtype=float).reshape(1, -1)
    prediction = int(model.predict(X)[0])
    probability = model.predict_proba(X)[0].tolist()
    latency_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "request_id=%s prediction=%d class=%s latency_ms=%.2f",
        request_id,
        prediction,
        target_names[prediction],
        latency_ms,
    )

    return PredictResponse(
        request_id=request_id,
        prediction=prediction,
        class_name=target_names[prediction],
        probability=probability,
        latency_ms=round(latency_ms, 3),
    )


@app.post("/predict/batch", tags=["inference"])
def predict_batch(requests: list[PredictRequest]) -> list[PredictResponse]:
    """複数サンプルをまとめて予測します（最大 100 件）。"""
    if len(requests) > 100:
        raise HTTPException(status_code=400, detail="一度に送れるサンプルは最大 100 件です。")
    return [predict(req) for req in requests]
