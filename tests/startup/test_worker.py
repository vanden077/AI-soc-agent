import asyncio
from unittest.mock import MagicMock

from src.api.services import JobProgressService
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
        job_key_prefix=mock_settings.REDIS_JSON_DOCUMENT_KEY,
        job_ttl=mock_settings.REDIS_JOBS_TTL,
        poll_interval=mock_settings.WORKER_POLL_INTERVAL,
        progress_service=None,
    )
    mock_worker_cls.return_value.run.assert_awaited_once()


async def test_start_analysis_worker_forwards_progress_service(
        mocker,
        mock_settings: Settings,
) -> None:
    """Forwards optional JobProgressService instance to AnalysisWorker."""
    mock_progress = MagicMock(spec=JobProgressService)
    mock_worker_cls = mocker.patch("src.startup.worker.AnalysisWorker")
    mock_worker_cls.return_value.run = mocker.AsyncMock(return_value=None)

    task = start_analysis_worker(
        settings=mock_settings,
        json_engine=MagicMock(),
        queue_engine=MagicMock(),
        llm_engine=MagicMock(),
        embedding_engine=MagicMock(),
        vector_engine=MagicMock(),
        progress_service=mock_progress,
    )
    await task

    assert mock_worker_cls.call_args.kwargs["progress_service"] is mock_progress
