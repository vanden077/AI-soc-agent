import asyncio
from unittest.mock import MagicMock

from src.constants import Settings
from src.startup.worker import start_analysis_worker


async def test_start_analysis_worker_schedules_background_task(
        mocker,
        mock_settings: Settings,
) -> None:
    """Nominal: instantiates AnalysisWorker with settings/engines and schedules an asyncio.Task."""
    mock_json = MagicMock()
    mock_queue = MagicMock()
    mock_llm = MagicMock()
    mock_embedding = MagicMock()
    mock_vector = MagicMock()

    mock_worker_cls = mocker.patch("src.startup.worker.AnalysisWorker")
    mock_worker_cls.return_value.run = mocker.AsyncMock(return_value=None)

    task = start_analysis_worker(
        settings=mock_settings,
        json_engine=mock_json,
        queue_engine=mock_queue,
        llm_engine=mock_llm,
        embedding_engine=mock_embedding,
        vector_engine=mock_vector,
    )

    assert isinstance(task, asyncio.Task)
    await task

    mock_worker_cls.assert_called_once_with(
        json_engine=mock_json,
        queue_engine=mock_queue,
        llm_engine=mock_llm,
        embedding_engine=mock_embedding,
        vector_engine=mock_vector,
        job_ttl=mock_settings.REDIS_JOBS_TTL,
        poll_interval=mock_settings.WORKER_POLL_INTERVAL,
    )
    mock_worker_cls.return_value.run.assert_awaited_once()
