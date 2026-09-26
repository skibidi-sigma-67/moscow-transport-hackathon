from sqlalchemy.ext.asyncio import AsyncSession

from commons.enums import RiskLevel

from .models import PredictionLog


class PredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_prediction(
        self,
        tr_id: int,
        predicted_delay_s: float,
        risk_level: RiskLevel,
        pattern_reason: str | None = None,
        status: str = "OK",
        error_text: str | None = None,
    ) -> PredictionLog:
        log = PredictionLog(
            tr_id=tr_id,
            predicted_delay_s=predicted_delay_s,
            risk_level=risk_level.value,
            pattern_reason=pattern_reason,
            status=status,
            error_text=error_text,
        )

        self.session.add(log)
        await self.session.flush()

        return log
