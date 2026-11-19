import logging
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.api.schemas import (
    AnalysisQueuedResponse,
    AvailablePlatforms,
    JobStatus,
    LogIngressPayload,
)
from src.constants import Settings


def test_ingest_and_process_log_nominal_returns_202_and_queued_response(
        mocker,
        mock_client: TestClient,
        mock_settings: Settings,
        mock_json_cache: MagicMock,
        mock_queue_cache: MagicMock,
        caplog,
) -> None:
    """Nominal: extracts engines/settings from request.state, normalizes platform, and notifies progress."""
    with caplog.at_level(logging.INFO):
        expected_response = AnalysisQueuedResponse(
            job_id="123e4567-e89b-12d3-a456-426614174000",
            status=JobStatus.PENDING,
            queue_size=1,
        )

        mock_service_cls = mocker.patch(
            "src.api.routers.threat_analyzer.AnalysisQueueService"
        )
        mock_service_cls.return_value.submit_log.return_value = expected_response
        mock_notify = mocker.patch(
            "src.api.routers.threat_analyzer.JobProgressService.notify_progress",
            new_callable=AsyncMock,
        )

        response = mock_client.post(
            "/threat_analyzer",
            json={
                "platform": "  WINDOWS  ",
                "raw_log": "EventID=10 TargetImage=lsass.exe",
            },
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_service_cls.assert_called_once_with(
            json_engine=mock_json_cache,
            queue_engine=mock_queue_cache,
            max_pending_size=mock_settings.REDIS_QUEUE_MAX_PENDING_SIZE,
            job_ttl=mock_settings.REDIS_JOBS_TTL,
            job_key_prefix=mock_settings.REDIS_JSON_DOCUMENT_KEY,
        )
        mock_service_cls.return_value.submit_log.assert_called_once_with(
            payload=LogIngressPayload(
                platform=AvailablePlatforms.WINDOWS,
                raw_log="EventID=10 TargetImage=lsass.exe",
            )
        )
        mock_notify.assert_awaited_once()
        assert response.json() == expected_response.model_dump(mode="json")
        assert (
                "[THREAT ROUTER] Received ingress log request for platform: 'windows'"
                in caplog.text
        )


def test_ingest_and_process_log_propagates_429_when_queue_is_full(
        mocker,
        mock_client: TestClient,
) -> None:
    """Backpressure: returns HTTP 429 when AnalysisQueueService rejects due to full queue."""
    mock_service_cls = mocker.patch(
        "src.api.routers.threat_analyzer.AnalysisQueueService"
    )
    mock_service_cls.return_value.submit_log.side_effect = HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Analysis queue capacity reached. Please retry later.",
    )

    response = mock_client.post(
        "/threat_analyzer",
        json={
            "platform": "linux",
            "raw_log": "sudo cat /etc/shadow",
        },
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_ingest_and_process_log_propagates_500_when_queue_service_fails(
        mocker,
        mock_client: TestClient,
) -> None:
    """Error propagation: returns HTTP 500 when AnalysisQueueService raises HTTPException."""
    mock_service_cls = mocker.patch(
        "src.api.routers.threat_analyzer.AnalysisQueueService"
    )
    mock_service_cls.return_value.submit_log.side_effect = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    response = mock_client.post(
        "/threat_analyzer",
        json={
            "platform": "linux",
            "raw_log": "sudo cat /etc/shadow",
        },
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_ingest_and_process_log_returns_422_on_invalid_payload(
        mock_client: TestClient,
) -> None:
    """Validation boundary: rejects unknown platform with HTTP 422 Unprocessable Entity."""
    response = mock_client.post(
        "/threat_analyzer",
        json={
            "platform": "unsupported_os",
            "raw_log": "some log",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
