from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.mixins import IdMixin, TimestampMixin


class SchedulePlan(Base, IdMixin, TimestampMixin):
    __tablename__ = "schedule_plans"

    tr_id: Mapped[int] = mapped_column(Integer, index=True)
    stop_id: Mapped[int] = mapped_column(BigInteger, index=True)
    time_begin: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
