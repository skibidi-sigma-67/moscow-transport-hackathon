from fastapi import APIRouter, HTTPException

from backend.modules.predictions.api.dependencies import PredictionServiceDependency
from commons.contracts.v1.api.predictions import PredictionLogDto

predictions_router = APIRouter(
    prefix="/predictions",
    tags=["Predictions"],
)


@predictions_router.post(
    "/{tr_id}/trigger",
    summary="Сгенерировать предсказание",
    description="Запускает процесс агрегации признаков для транспортного средства и обращается к ML-модели для получения прогноза задержек и оценки риска.",
    response_description="Журнал выполненного предсказания с задержкой и уровнем риска",
)
async def trigger_prediction(
    tr_id: int,
    service: PredictionServiceDependency,
) -> PredictionLogDto:
    try:
        result = await service.generate_prediction(tr_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
