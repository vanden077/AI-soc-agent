from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from src.api.routers.rt_threat_analysis_progress import (
    _READ_ONLY_NOTICE,
    stream_job_progress,
)


def test_stream_job_progress_sends_initial_snapshot_and_read_only_notice(
        mock_client: TestClient,
        mock_queue_cache: MagicMock,
) -> None:
    """Streams initial snapshot on connect, replies with read-only notice on inbound data, and cleans up."""
    mock_queue_cache.get_done.return_value = ["job:1", "job:2"]
    mock_queue_cache.pending_size.return_value = 1

    with mock_client.websocket_connect("/threat_analyzer/progress") as ws:
        initial = ws.receive_json()
        assert initial == {
            "processed": 2,
            "total": 3,
            "pending": 1,
            "in_progress": 0,
        }

        ws.send_text("hello server")
        notice = ws.receive_json()
        assert notice == _READ_ONLY_NOTICE
        assert "read-only channel" in notice["notice"]


@pytest.mark.asyncio
async def test_stream_job_progress_handles_websocket_disconnect_exception() -> None:
    """Covers WebSocketDisconnect exception branch and ensures manager.disconnect is always called."""
    ws = AsyncMock()
    ws.state.ws_manager = MagicMock()
    ws.state.ws_manager.connect = AsyncMock()
    ws.state.progress_service = MagicMock()
    ws.state.progress_service.get_snapshot.return_value = {"processed": 0, "total": 0}
    ws.receive.side_effect = WebSocketDisconnect(code=1000)

    await stream_job_progress(ws)

    ws.state.ws_manager.connect.assert_awaited_once_with(ws)
    ws.send_json.assert_awaited_once_with({"processed": 0, "total": 0})
    ws.state.ws_manager.disconnect.assert_called_once_with(ws)
