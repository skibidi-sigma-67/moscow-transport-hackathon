from pathlib import Path

import uvicorn
from fastapi import FastAPI

from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.contracts.v1.ml.responses import MLPredictionResponse

from .model import DelayPredictionModel

MODEL_PATH = Path(__file__).parent / "data" / "delay_model.json"

app = FastAPI(
    title="Moscow Transport Delay Model",
    version="0.1.0",
)
model = DelayPredictionModel.load(MODEL_PATH)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=MLPredictionResponse)
async def predict(request: MLPredictionRequest) -> MLPredictionResponse:
    return model.predict(request)


if __name__ == "__main__":
    uvicorn.run(
        "backend.ml_service.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
    )
