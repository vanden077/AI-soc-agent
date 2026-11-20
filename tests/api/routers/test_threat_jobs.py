from collections.abc import Callable
from unittest.mock import MagicMock

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.api.schemas import (
    AnalysisJobRecord,
    AnalysisQueuedResponse,
    JobStatus,
)
from src.constants import Settings


def test_list_pending_jobs_nominal_returns_200_and_queued_list(
        mocker,
        mock_client: TestClient,
        mock_settings: Settings,
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> None:
    """Nominal: instantiates JobQueryService from request.state and returns pending jobs."""
    expected = [
        AnalysisQueuedResponse(
            job_id="123e4567-e89b-12d3-a456-426614174000",
            status=JobStatus.PENDING,
            queue_size=1,
        )
    ]
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_pending_jobs.return_value = expected

    response = mock_client.get("/threat_analysis/pending")

    assert response.status_code == status.HTTP_200_OK
    mock_service_cls.assert_called_once_with(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        job_key_prefix=mock_settings.REDIS_JSON_DOCUMENT_KEY,
    )
    mock_service_cls.return_value.get_pending_jobs.assert_called_once_with()
    assert response.json() == [item.model_dump(mode="json") for item in expected]


def test_list_pending_jobs_propagates_500_when_query_service_fails(
        mocker,
        mock_client: TestClient,
) -> None:
    """Error propagation: returns HTTP 500 when JobQueryService raises HTTPException."""
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_pending_jobs.side_effect = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    response = mock_client.get("/threat_analysis/pending")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_list_done_jobs_nominal_returns_200_and_records_list(
        mocker,
        mock_client: TestClient,
        mock_settings: Settings,
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
        sample_job_record_factory: Callable[..., AnalysisJobRecord],
) -> None:
    """Nominal: instantiates JobQueryService from request.state and returns completed job records."""
    expected = [
        sample_job_record_factory(
            job_id="123e4567-e89b-12d3-a456-426614174001",
            job_status=JobStatus.COMPLETED,
        )
    ]
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_done_jobs.return_value = expected

    response = mock_client.get("/threat_analysis/done")

    assert response.status_code == status.HTTP_200_OK
    mock_service_cls.assert_called_once_with(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        job_key_prefix=mock_settings.REDIS_JSON_DOCUMENT_KEY,
    )
    mock_service_cls.return_value.get_done_jobs.assert_called_once_with()
    assert response.json() == [item.model_dump(mode="json") for item in expected]


def test_list_done_jobs_propagates_500_when_query_service_fails(
        mocker,
        mock_client: TestClient,
) -> None:
    """Error propagation: returns HTTP 500 when JobQueryService raises HTTPException."""
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_done_jobs.side_effect = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    response = mock_client.get("/threat_analysis/done")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_get_job_status_nominal_returns_200_and_job_record(
        mocker,
        mock_client: TestClient,
        mock_settings: Settings,
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
        sample_job_record_factory: Callable[..., AnalysisJobRecord],
) -> None:
    """Nominal: validates UUID path parameter, delegates to JobQueryService, and returns 200 OK."""
    job_id = "123e4567-e89b-12d3-a456-426614174002"
    expected = sample_job_record_factory(job_id=job_id, job_status=JobStatus.COMPLETED)
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_job.return_value = expected

    response = mock_client.get(f"/threat_analysis/job/{job_id}")

    assert response.status_code == status.HTTP_200_OK
    mock_service_cls.assert_called_once_with(
        json_engine=mock_json_cache,
        queue_engine=mock_queue_cache,
        job_key_prefix=mock_settings.REDIS_JSON_DOCUMENT_KEY,
    )
    mock_service_cls.return_value.get_job.assert_called_once_with(job_id=job_id)
    assert response.json() == expected.model_dump(mode="json")


def test_get_job_status_propagates_404_when_job_not_found(
        mocker,
        mock_client: TestClient,
) -> None:
    """Not found: propagates HTTP 404 when JobQueryService cannot locate the job record."""
    job_id = "123e4567-e89b-12d3-a456-426614174003"
    mock_service_cls = mocker.patch("src.api.routers.threat_jobs.JobQueryService")
    mock_service_cls.return_value.get_job.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Analysis job '{job_id}' not found or expired.",
    )

    response = mock_client.get(f"/threat_analysis/job/{job_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_job_status_returns_422_on_invalid_uuid(
        mock_client: TestClient,
) -> None:
    """Validation boundary: rejects malformed UUID path parameter with HTTP 422."""
    response = mock_client.get("/threat_analysis/job/not-a-valid-uuid")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
