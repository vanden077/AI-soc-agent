from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from src.api.schemas import (
    AnalysisJobRecord,
    AvailablePlatforms,
    JobStatus,
    LogIngressPayload,
)
from src.api.services import AnalysisQueueService


def test_submit_log_nominal_persists_job_and_enqueues(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Nominal: checks capacity, persists PENDING AnalysisJobRecord, and pushes job_id to FIFO queue."""
    mock_queue_cache.pending_size.return_value = 2
    mock_json_cache.insert.return_value = True
    mock_queue_cache.enqueue.return_value = 3

    payload = LogIngressPayload(
        platform=AvailablePlatforms.WINDOWS,
        raw_log="EventID=4688 New Process Created",
    )
    service = AnalysisQueueService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        max_pending_size=10,
        job_ttl=3600,
    )

    result = service.submit_log(payload=payload)

    assert UUID(result.job_id)
    assert result.status == JobStatus.PENDING
    assert result.queue_size == 3

    mock_json_cache.insert.assert_called_once()
    call_kwargs = mock_json_cache.insert.call_args.kwargs
    assert call_kwargs["key"] == f"job:{result.job_id}"
    assert call_kwargs["ttl"] == 3600

    stored_record = AnalysisJobRecord.model_validate(call_kwargs["data"])
    assert stored_record.job_id == result.job_id
    assert stored_record.status == JobStatus.PENDING
    assert stored_record.log_ingress_payload == payload
    assert stored_record.analysis is None
    assert stored_record.error is None

    mock_queue_cache.enqueue.assert_called_once_with(result.job_id)


def test_submit_log_raises_429_when_queue_at_max_capacity(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Backpressure: raises HTTP 429 and avoids storage/enqueue when pending_size >= max_pending_size."""
    mock_queue_cache.pending_size.return_value = 5
    payload = LogIngressPayload(
        platform=AvailablePlatforms.LINUX,
        raw_log="sshd failed password",
    )
    service = AnalysisQueueService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        max_pending_size=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.submit_log(payload=payload)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    mock_json_cache.insert.assert_not_called()
    mock_queue_cache.enqueue.assert_not_called()


def test_submit_log_raises_500_when_pending_size_check_fails(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Broker failure: translates pending_size exception into opaque HTTP 500."""
    mock_queue_cache.pending_size.side_effect = ConnectionError("Redis unreachable")
    payload = LogIngressPayload(
        platform=AvailablePlatforms.LINUX,
        raw_log="sshd failed password",
    )
    service = AnalysisQueueService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.submit_log(payload=payload)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Internal Server Error"
    mock_json_cache.insert.assert_not_called()


def test_submit_log_raises_500_when_json_insert_returns_false(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Persistence failure: raises opaque HTTP 500 and avoids enqueue if JSON insert returns False."""
    mock_queue_cache.pending_size.return_value = 0
    mock_json_cache.insert.return_value = False
    payload = LogIngressPayload(
        platform=AvailablePlatforms.MACOS,
        raw_log="sudo launchctl load",
    )
    service = AnalysisQueueService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.submit_log(payload=payload)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Internal Server Error"
    mock_queue_cache.enqueue.assert_not_called()


def test_submit_log_rolls_back_json_record_and_raises_500_when_enqueue_fails(
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Rollback: deletes persisted JSON record and raises opaque HTTP 500 if enqueue crashes."""
    mock_queue_cache.pending_size.return_value = 0
    mock_json_cache.insert.return_value = True
    mock_queue_cache.enqueue.side_effect = ConnectionError("LPUSH failed")
    payload = LogIngressPayload(
        platform=AvailablePlatforms.CONTAINERS,
        raw_log="docker run --privileged",
    )
    service = AnalysisQueueService(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.submit_log(payload=payload)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Internal Server Error"
    inserted_key = mock_json_cache.insert.call_args.kwargs["key"]
    mock_json_cache.delete.assert_called_once_with(inserted_key)
