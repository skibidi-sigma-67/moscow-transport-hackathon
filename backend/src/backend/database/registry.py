from backend.database.base import Base
from backend.modules.predictions.models import PredictionLog
from backend.modules.reference.models import DeviceMapping
from backend.modules.schedule.models import SchedulePlan

__all__ = ["Base", "PredictionLog", "DeviceMapping", "SchedulePlan", "target_metadata"]

target_metadata = Base.metadata
