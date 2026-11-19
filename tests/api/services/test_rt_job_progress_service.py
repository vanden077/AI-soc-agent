import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.services import JobProgressService
from src.api.websocket import WebSocketConnectionManager


@pytest.fixture
def mock_connection_manager() -> MagicMock:
    """Return an isolated mock for WebSocketConnectionManager."""
    manager = MagicMock(spec=WebSocketConnectionManager)
    manager.broadcast_json = AsyncMock()
    return manager


@pytest.fixture
def progress_service(
        mock_queue_cache: MagicMock,
        mock_connection_manager: MagicMock,
) -> JobProgressService:
    """Return a configured JobProgressService backed by mocks."""
    return JobProgressService(
        queue_engine=mock_queue_cache,
        connection_manager=mock_connection_manager,
    )


def test_get_snapshot_computes_totals_and_tracks_in_flight_jobs(
        progress_service: JobProgressService,
        mock_queue_cache: MagicMock,
) -> None:
    """Computes processed, pending, in_progress, and total accurately and clamps in_progress >= 0."""
    mock_queue_cache.get_done.return_value = ["job:1", "job:2"]
    mock_queue_cache.pending_size.return_value = 3

    assert progress_service.get_snapshot() == {
        "processed": 2,
        "total": 5,
        "pending": 3,
        "in_progress": 0,
    }

    progress_service.job_started()
    progress_service.job_started()
    assert progress_service.get_snapshot() == {
        "processed": 2,
        "total": 7,
        "pending": 3,
        "in_progress": 2,
    }

    progress_service.job_finished()
    progress_service.job_finished()
    progress_service.job_finished()
    assert progress_service.get_snapshot()["in_progress"] == 0


@pytest.mark.asyncio
async def test_notify_progress_broadcasts_snapshot(
        progress_service: JobProgressService,
        mock_queue_cache: MagicMock,
        mock_connection_manager: MagicMock,
) -> None:
    """Computes current snapshot and broadcasts it to active WebSocket clients."""
    mock_queue_cache.get_done.return_value = ["job:1"]
    mock_queue_cache.pending_size.return_value = 1

    await progress_service.notify_progress()

    mock_connection_manager.broadcast_json.assert_awaited_once_with(
        {
            "processed": 1,
            "total": 2,
            "pending": 1,
            "in_progress": 0,
        }
    )


@pytest.mark.asyncio
async def test_notify_progress_logs_warning_when_broadcast_fails(
        progress_service: JobProgressService,
        mock_queue_cache: MagicMock,
        mock_connection_manager: MagicMock,
        caplog,
) -> None:
    """Logs a warning without raising when snapshot computation or broadcast fails."""
    mock_queue_cache.get_done.side_effect = RuntimeError("Redis timeout")

    with caplog.at_level(logging.WARNING):
        await progress_service.notify_progress()

    mock_connection_manager.broadcast_json.assert_not_awaited()
    assert "[PROGRESS SERVICE] Failed to broadcast job progress: Redis timeout" in caplog.messages
