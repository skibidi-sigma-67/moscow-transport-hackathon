from fastapi import APIRouter, HTTPException, Request

from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.contracts.v1.ml.responses import MLPredictionResponse

router = APIRouter()


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "model": request.app.state.predictor.model_version,
    }


@router.post("/predict", response_model=MLPredictionResponse)
def predict(request: Request, payload: MLPredictionRequest):
    try:
        return request.app.state.predictor.predict(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
