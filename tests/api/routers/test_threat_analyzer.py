import logging
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import pytest

from src.api.schemas import AvailablePlatforms
from src.soc_agent.schemas import MitreTechnique, ThreatAnalysis


def test_ingest_and_process_log_nominal_returns_200_and_threat_analysis(
    mocker,
    mock_client: TestClient,
    mock_llm_engine: MagicMock,
    mock_embedding_engine: MagicMock,
    mock_vector_cache: MagicMock,
    caplog,
) -> None:
    """Nominal: extracts engines from request.state, normalizes platform, and returns ThreatAnalysis."""
    with caplog.at_level(logging.INFO):
        expected_report = ThreatAnalysis(
            platform=AvailablePlatforms.WINDOWS,
            is_threat=True,
            confidence_score=0.94,
            semantic_summary="Suspicious PowerShell execution attempting LSASS memory access.",
            matched_techniques=[
                MitreTechnique(
                    mitre_id="T1003.001",
                    parent_id="T1003",
                    technic_name="LSASS Memory",
                    tactics="Credential Access",
                    description="Adversaries may attempt to access credential material stored in LSASS.",
                    platforms="windows",
                    normalized_similarity=0.91,
                )
            ],
        )

        mock_service_cls = mocker.patch("src.api.routers.threat_analyzer.ForensicService")
        mock_service_cls.return_value.analyze_and_report = AsyncMock(return_value=expected_report)

        response = mock_client.post(
            "/threat_analyzer",
            json={
                "platform": "  WINDOWS  ",
                "raw_log": "EventID=10 TargetImage=lsass.exe",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service_cls.assert_called_once_with(
            llm_engine=mock_llm_engine,
            embedding_engine=mock_embedding_engine,
            vector_engine=mock_vector_cache,
        )
        mock_service_cls.return_value.analyze_and_report.assert_awaited_once_with(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="EventID=10 TargetImage=lsass.exe",
        )
        assert response.json() == expected_report.model_dump(mode="json")
        assert "[THREAT ROUTER] Received ingress log request for platform: 'windows'" in caplog.text


def test_ingest_and_process_log_propagates_500_when_forensic_service_fails(
    mocker,
    mock_client: TestClient,
) -> None:
    """Error propagation: returns HTTP 500 when ForensicService raises HTTPException."""
    mock_service_cls = mocker.patch("src.api.routers.threat_analyzer.ForensicService")
    mock_service_cls.return_value.analyze_and_report = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
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