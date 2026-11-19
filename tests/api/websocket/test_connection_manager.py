from unittest.mock import AsyncMock

import pytest

from src.api.websocket import WebSocketConnectionManager


@pytest.mark.asyncio
async def test_connect_and_disconnect_updates_active_count() -> None:
    """Ensure connect accepts the socket, increments active_count, and disconnect removes it."""
    manager = WebSocketConnectionManager()
    ws = AsyncMock()

    assert manager.active_count == 0
    await manager.connect(ws)
    ws.accept.assert_awaited_once()
    assert manager.active_count == 1

    manager.disconnect(ws)
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_broadcast_json_noop_when_no_clients() -> None:
    """Ensure broadcast_json returns cleanly without error when no clients are connected."""
    manager = WebSocketConnectionManager()
    await manager.broadcast_json({"processed": 1, "total": 2})
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_broadcast_json_sends_to_all_and_prunes_broken_clients() -> None:
    """Ensure broadcast_json delivers payload to healthy clients and removes failing sockets."""
    manager = WebSocketConnectionManager()
    healthy_ws = AsyncMock()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = RuntimeError("Socket closed")

    await manager.connect(healthy_ws)
    await manager.connect(broken_ws)
    assert manager.active_count == 2

    payload = {"processed": 3, "total": 5}
    await manager.broadcast_json(payload)

    healthy_ws.send_json.assert_awaited_once_with(payload)
    broken_ws.send_json.assert_awaited_once_with(payload)
    assert manager.active_count == 1
