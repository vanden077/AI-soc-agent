from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from src.api.schemas import (
    AnalysisJobRecord,
    JobStatus,
)
from src.api.services import JobQueryService

JOB_KEY_PREFIX = "job:"


@pytest.fixture
def query_service(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> JobQueryService:
    """Return a configured JobQueryService backed by mock engines."""
    return JobQueryService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        job_key_prefix=JOB_KEY_PREFIX,
    )


def test_get_pending_jobs_nominal_returns_queued_responses(
        query_service: JobQueryService,
        mock_queue_cache: MagicMock,
) -> None:
    """Nominal: strips key prefix and projects pending keys into AnalysisQueuedResponse items."""
    mock_queue_cache.get_pending.return_value = ["job:job-1", "job:job-2"]

    result = query_service.get_pending_jobs()

    assert len(result) == 2
    assert result[0].job_id == "job-1"
    assert result[0].status == JobStatus.PENDING
    assert result[0].queue_size == 2
    assert result[1].job_id == "job-2"
    assert result[1].queue_size == 2


def test_get_pending_jobs_empty_returns_empty_list(
        query_service: JobQueryService,
        mock_queue_cache: MagicMock,
) -> None:
    """Nominal empty: returns an empty list when no jobs are pending."""
    mock_queue_cache.get_pending.return_value = []

    assert query_service.get_pending_jobs() == []


def test_get_pending_jobs_raises_500_when_queue_fails(
        query_service: JobQueryService,
        mock_queue_cache: MagicMock,
) -> None:
    """Broker failure: translates get_pending exception into opaque HTTP 500."""
    mock_queue_cache.get_pending.side_effect = ConnectionError("Redis unreachable")

    with pytest.raises(HTTPException) as exc_info:
        query_service.get_pending_jobs()

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Internal Server Error"


def test_get_done_jobs_nominal_and_skips_expired_records(
        query_service: JobQueryService,
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
        sample_job_record_factory: Callable[..., AnalysisJobRecord],
) -> None:
    """Nominal + TTL edge case: hydrates existing done records and skips expired keys."""
    record_1 = sample_job_record_factory("job-1", JobStatus.COMPLETED)
    record_3 = sample_job_record_factory("job-3", JobStatus.FAILED)

    mock_queue_cache.get_done.return_value = ["job:job-1", "job:job-expired", "job:job-3"]
    mock_json_cache.get.side_effect = [
        record_1.model_dump(mode="json"),
        None,
        record_3.model_dump(mode="json"),
    ]

    result = query_service.get_done_jobs()

    assert [r.job_id for r in result] == ["job-1", "job-3"]
    assert result[0].status == JobStatus.COMPLETED
    assert result[1].status == JobStatus.FAILED


def test_get_done_jobs_raises_500_when_queue_fails(
        query_service: JobQueryService,
        mock_queue_cache: MagicMock,
) -> None:
    """Broker failure: translates get_done exception into opaque HTTP 500."""
    mock_queue_cache.get_done.side_effect = ConnectionError("Redis unreachable")

    with pytest.raises(HTTPException) as exc_info:
        query_service.get_done_jobs()

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Internal Server Error"


def test_get_job_nominal_returns_validated_record(
        query_service: JobQueryService,
        mock_json_cache: MagicMock,
        sample_job_record_factory: Callable[..., AnalysisJobRecord],
) -> None:
    """Nominal: retrieves persisted job document and validates it into AnalysisJobRecord."""
    expected = sample_job_record_factory("job-42", JobStatus.COMPLETED)
    mock_json_cache.get.return_value = expected.model_dump(mode="json")

    result = query_service.get_job("job-42")

    mock_json_cache.get.assert_called_once_with("job:job-42")
    assert result == expected


def test_get_job_raises_404_when_missing_or_expired(
        query_service: JobQueryService,
        mock_json_cache: MagicMock,
) -> None:
    """Missing/expired: raises HTTP 404 when JSON storage returns None."""
    mock_json_cache.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        query_service.get_job("missing-id")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Analysis job 'missing-id' not found or expired."
