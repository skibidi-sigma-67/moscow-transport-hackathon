from datetime import datetime

from pydantic import Field

from commons.pydantic.models import FrozenModel


class DeviceMappingDto(FrozenModel):
    id: int = Field(..., description="Внутренний идентификатор привязки")
    unit_id: int = Field(
        ..., description="Идентификатор бортового оборудования (трекера)"
    )
    tr_id: int = Field(..., description="Идентификатор транспортного средства")
    created_at: datetime = Field(..., description="Время создания записи")
    updated_at: datetime = Field(..., description="Время последнего обновления записи")
