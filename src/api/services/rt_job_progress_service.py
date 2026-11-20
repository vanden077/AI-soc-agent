import asyncio
import logging
from typing import Any

from src.api.websocket import WebSocketConnectionManager
from src.persistence.interfaces import IQueueEngine

logger = logging.getLogger(__name__)


class JobProgressService:
    """
    Application service computing real-time forensic job progress (X / Y processed)
    and broadcasting updates to connected WebSocket clients.
    """

    def __init__(
            self,
            queue_engine: IQueueEngine,
            connection_manager: WebSocketConnectionManager,
    ) -> None:
        self._queue_engine = queue_engine
        self._connection_manager = connection_manager
        self._in_progress: int = 0

    def job_started(self) -> None:
        """Mark one dequeued job as currently in flight."""
        self._in_progress += 1

    def job_finished(self) -> None:
        """Mark one in-flight job as finished."""
        self._in_progress = max(0, self._in_progress - 1)

    def get_snapshot(self) -> dict[str, Any]:
        """Compute the current progress snapshot (processed / total) from the queue engine."""
        done = len(self._queue_engine.get_done())
        pending = self._queue_engine.pending_size()
        in_progress = self._in_progress
        total = done + pending + in_progress
        return {
            "processed": done,
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
        }

    async def notify_progress(self) -> None:
        """Compute and broadcast the latest job progress snapshot to active WebSocket clients."""
        try:
            snapshot = await asyncio.to_thread(self.get_snapshot)
            await self._connection_manager.broadcast_json(snapshot)
        except Exception as err:
            logger.warning(f"[PROGRESS SERVICE] Failed to broadcast job progress: {str(err)}")
