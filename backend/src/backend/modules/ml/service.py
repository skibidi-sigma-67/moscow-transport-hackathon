import httpx

from backend.settings import Settings
from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import PredictionStatus, RiskLevel


class MLService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check_health(self) -> str:
        ml_status = "error"

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(self.settings.ml.health_url)
                if response.status_code == 200:
                    ml_status = "ok"
                else:
                    ml_status = f"error_{response.status_code}"
        except Exception:
            ml_status = "unreachable"

        return ml_status

    async def get_prediction(
        self, request: MLPredictionRequest, fallback_delay_s: float
    ) -> tuple[MLPredictionResponse, str | None]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.ml.timeout) as client:
                response = await client.post(
                    self.settings.ml.url,
                    json=request.model_dump(mode="json"),
                )
                response.raise_for_status()

                ml_resp = MLPredictionResponse.model_validate_json(response.read())
                return ml_resp, None
        except Exception as e:
            if fallback_delay_s > 300:
                risk = RiskLevel.RED
            elif fallback_delay_s > 120:
                risk = RiskLevel.YELLOW
            else:
                risk = RiskLevel.GREEN

            ml_resp = MLPredictionResponse(
                predicted_delay_s=fallback_delay_s,
                risk_level=risk,
                pattern_reason=None,
                status=PredictionStatus.UNAVAILABLE,
            )
            return ml_resp, f"ML Error: {e}"
