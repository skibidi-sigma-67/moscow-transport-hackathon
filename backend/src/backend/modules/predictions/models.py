from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.mixins import IdMixin, TimestampMixin


class PredictionLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "prediction_logs"

    tr_id: Mapped[int] = mapped_column(Integer, index=True)
    predicted_delay_s: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(32))
    pattern_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="OK")
    error_text: Mapped[str | None] = mapped_column(String, nullable=True)
