import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.modules.predictions.repository import PredictionRepository
from backend.modules.predictions.service import PredictionService
from backend.modules.schedule.repository import ScheduleRepository
from backend.modules.schedule.service import ScheduleService
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.modules.telemetry.service import TelemetryService
from backend.settings import Settings

logger = logging.getLogger(__name__)


class PredictionWorker:
    def __init__(
        self,
        name: str,
        redis_client: Redis,
        session_maker: async_sessionmaker,
        settings: Settings,
        target_cycle_time_s: float = 30.0,
    ) -> None:
        self.name = name
        self.redis = redis_client
        self.session_maker = session_maker
        self.settings = settings
        self.target_cycle_time_s = target_cycle_time_s
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError(f"Worker {self.name} already started")

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name=self.name)
        logger.info("Worker %s started", self.name)

    async def stop(self) -> None:
        if self._task is None:
            return

        self._stop_event.set()

        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except TimeoutError:
            logger.warning("Worker %s did not stop gracefully, cancelling", self.name)
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._task = None
        logger.info("Worker %s stopped", self.name)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                keys = await self.redis.keys("telemetry:point:*")
                tr_ids = []

                for k in keys:
                    try:
                        tr_ids.append(int(k.decode("utf-8").split(":")[-1]))
                    except ValueError, AttributeError:
                        continue

                if not tr_ids:
                    await self._sleep_with_stop(5.0)
                    continue

                delay_per_vehicle = self.target_cycle_time_s / len(tr_ids)

                for tr_id in tr_ids:
                    if self._stop_event.is_set():
                        break

                    try:
                        await self._process_vehicle(tr_id)
                    except Exception:
                        logger.exception(
                            "Error processing predictions for tr_id %d",
                            tr_id,
                        )

                    await self._sleep_with_stop(delay_per_vehicle)

            except Exception:
                logger.exception("Worker %s crashed in outer loop", self.name)
                await self._sleep_with_stop(5.0)

    async def _process_vehicle(self, tr_id: int) -> None:
        async with self.session_maker() as session:
            prediction_repo = PredictionRepository(session)
            telemetry_repo = TelemetryRedisRepository(self.redis, self.settings)
            schedule_repo = ScheduleRepository(session)

            telemetry_service = TelemetryService(telemetry_repo)
            schedule_service = ScheduleService(schedule_repo)

            service = PredictionService(
                repository=prediction_repo,
                telemetry_service=telemetry_service,
                redis_client=self.redis,
                schedule_service=schedule_service,
                settings=self.settings,
            )
            await service.generate_prediction(tr_id)

    async def _sleep_with_stop(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass
