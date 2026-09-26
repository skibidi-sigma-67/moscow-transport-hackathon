from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.mixins import IdMixin, TimestampMixin


class DeviceMapping(Base, IdMixin, TimestampMixin):
    __tablename__ = "device_mappings"

    unit_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    tr_id: Mapped[int] = mapped_column(Integer, index=True)
