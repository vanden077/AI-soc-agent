import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.api.schemas import (
    AnalysisJobRecord,
    AvailablePlatforms,
    JobStatus,
    LogIngressPayload,
)
from src.soc_agent.schemas import ThreatAnalysis
from src.worker import AnalysisWorker


def _build_worker() -> tuple[
    AnalysisWorker, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock
]:
    """Helper constructing an AnalysisWorker with isolated engine mocks."""
    json_engine = MagicMock()
    queue_engine = MagicMock()
    llm_engine = MagicMock()
    embedding_engine = MagicMock()
    vector_engine = MagicMock()

    worker = AnalysisWorker(
        json_engine=json_engine,
        queue_engine=queue_engine,
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_engine,
        job_ttl=3600,
        poll_interval=0.01,
    )
    return worker, json_engine, queue_engine, llm_engine, embedding_engine, vector_engine


async def test_process_next_job_returns_false_when_queue_empty() -> None:
    """Idle branch: returns False immediately without touching JSON storage when dequeue returns None."""
    worker, json_engine, queue_engine, *_ = _build_worker()
    queue_engine.dequeue.return_value = None

    processed = await worker.process_next_job()

    assert processed is False
    json_engine.get.assert_not_called()
    queue_engine.mark_done.assert_not_called()


async def test_process_next_job_skips_when_job_record_missing() -> None:
    """Missing/expired record branch: logs warning and returns True without running workflow."""
    worker, json_engine, queue_engine, *_ = _build_worker()
    queue_engine.dequeue.return_value = "missing-job-id"
    json_engine.get.return_value = None

    processed = await worker.process_next_job()

    assert processed is True
    json_engine.get.assert_called_once_with("job:missing-job-id")
    json_engine.insert.assert_not_called()
    queue_engine.mark_done.assert_not_called()


async def test_process_next_job_nominal_completes_and_marks_done(mocker) -> None:
    """Nominal: transitions job PENDING -> PROCESSING -> COMPLETED, persists analysis, and marks done."""
    worker, json_engine, queue_engine, llm_engine, embedding_engine, vector_engine = (
        _build_worker()
    )
    job_id = "job-123"
    record = AnalysisJobRecord(
        job_id=job_id,
        status=JobStatus.PENDING,
        log_ingress_payload=LogIngressPayload(
            platform=AvailablePlatforms.SAAS,
            raw_log="OAuth consent granted to suspicious app",
        ),
    )
    expected_analysis = ThreatAnalysis(
        platform=AvailablePlatforms.SAAS,
        is_threat=True,
        confidence_score=0.92,
        semantic_summary="Suspicious OAuth application consent.",
        matched_techniques=[],
    )

    queue_engine.dequeue.return_value = job_id
    json_engine.get.return_value = record.model_dump(mode="json")

    mock_forensic_cls = mocker.patch("src.worker.analysis_worker.ForensicService")
    mock_forensic_cls.return_value.analyze_and_report = AsyncMock(
        return_value=expected_analysis
    )

    processed = await worker.process_next_job()

    assert processed is True
    mock_forensic_cls.assert_called_once_with(
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_engine,
    )
    assert json_engine.insert.call_count == 2

    first_saved = AnalysisJobRecord.model_validate(
        json_engine.insert.call_args_list[0].kwargs["data"]
    )
    assert first_saved.status == JobStatus.PROCESSING

    second_saved = AnalysisJobRecord.model_validate(
        json_engine.insert.call_args_list[1].kwargs["data"]
    )
    assert second_saved.status == JobStatus.COMPLETED
    assert second_saved.analysis == expected_analysis
    assert second_saved.error is None

    queue_engine.mark_done.assert_called_once_with(job_id)


async def test_process_next_job_marks_failed_and_done_when_workflow_crashes(
        mocker,
) -> None:
    """Failure branch: records FAILED status with opaque error message and moves job to done."""
    worker, json_engine, queue_engine, *_ = _build_worker()
    job_id = "job-err"
    record = AnalysisJobRecord(
        job_id=job_id,
        status=JobStatus.PENDING,
        log_ingress_payload=LogIngressPayload(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="powershell -enc ...",
        ),
    )

    queue_engine.dequeue.return_value = job_id
    json_engine.get.return_value = record.model_dump(mode="json")

    mock_forensic_cls = mocker.patch("src.worker.analysis_worker.ForensicService")
    mock_forensic_cls.return_value.analyze_and_report = AsyncMock(
        side_effect=RuntimeError("Ollama timeout")
    )

    processed = await worker.process_next_job()

    assert processed is True
    assert json_engine.insert.call_count == 2

    final_saved = AnalysisJobRecord.model_validate(
        json_engine.insert.call_args_list[1].kwargs["data"]
    )
    assert final_saved.status == JobStatus.FAILED
    assert final_saved.analysis is None
    assert final_saved.error == "Forensic analysis failed."

    queue_engine.mark_done.assert_called_once_with(job_id)


async def test_run_polls_until_cancelled(mocker) -> None:
    """Loop lifecycle: processes active jobs immediately, sleeps when idle, and exits cleanly on cancel."""
    worker, *_ = _build_worker()
    call_count = 0

    async def _fake_process() -> bool:
        nonlocal call_count
        call_count += 1
        return call_count == 1

    mocker.patch.object(worker, "process_next_job", side_effect=_fake_process)

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.03)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert call_count >= 2
