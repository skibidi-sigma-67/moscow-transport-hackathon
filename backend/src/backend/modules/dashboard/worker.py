import asyncio
import logging

from backend.modules.dashboard.service import DashboardService
from backend.modules.dashboard.websocket_pool import WebsocketConnectionPool
from backend.settings import Settings

logger = logging.getLogger(__name__)

class DashboardWorker:
    def __init__(
        self,
        name: str,
        service: DashboardService,
        websocket_pool: WebsocketConnectionPool,
        settings: Settings,
    ) -> None:
        self.name = name
        self.service = service
        self.websocket_pool = websocket_pool
        self.settings = settings
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"Worker '{self.name}' started.")

    async def stop(self) -> None:
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Worker '{self.name}' stopped.")

    async def _run(self) -> None:
        update_interval = self.settings.app.dashboard_websocket_update_interval_s
        
        while self._running:
            try:
                if self.websocket_pool.active_connections:
                    state = await self.service.get_current_state()
                    await self.websocket_pool.broadcast(state.model_dump_json())
            except Exception as e:
                logger.error(f"Error in DashboardWorker: {e}")
            
            await asyncio.sleep(update_interval)
