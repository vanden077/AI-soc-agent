import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Lightweight transport manager tracking active FastAPI WebSocket clients
    and broadcasting JSON payloads with automatic stale-socket cleanup.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def active_count(self) -> int:
        """Return the number of currently connected WebSocket clients."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept an incoming WebSocket handshake and register the client."""
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a disconnected WebSocket client."""
        self._connections.discard(websocket)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        """Send a JSON payload to all active clients, pruning any broken connections."""
        if not self._connections:
            return

        stale: list[WebSocket] = []
        for connection in tuple(self._connections):
            try:
                await connection.send_json(payload)
            except Exception as err:
                logger.debug(f"[WS MANAGER] Dropping unreachable WebSocket client: {err!s}")
                stale.append(connection)

        for connection in stale:
            self.disconnect(connection)
