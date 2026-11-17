import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from src.api.schemas import AvailablePlatforms
from src.api.services.forensic_service import ForensicService
from src.soc_agent.schemas import ThreatAnalysis


async def test_analyze_and_report_nominal_delegates_to_workflow(
    mocker,
    mock_llm_engine: MagicMock,
    mock_embedding_engine: MagicMock,
    mock_vector_cache: MagicMock,
    caplog,
) -> None:
    """Nominal: instantiates SocAgentWorkflow with injected engines and returns ThreatAnalysis."""
    with caplog.at_level(logging.INFO):
        expected_report = ThreatAnalysis(
            platform=AvailablePlatforms.WINDOWS,
            is_threat=True,
            confidence_score=0.93,
            semantic_summary="Suspicious PowerShell execution targeting LSASS.",
            matched_techniques=[],
        )

        mock_workflow_cls = mocker.patch(
            "src.api.services.forensic_service.SocAgentWorkflow"
        )
        mock_workflow_cls.return_value.execute = AsyncMock(return_value=expected_report)

        service = ForensicService(
            llm_engine=mock_llm_engine,
            embedding_engine=mock_embedding_engine,
            vector_engine=mock_vector_cache,
        )
        result = await service.analyze_and_report(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="EventID=4688 powershell.exe -enc ...",
        )

        mock_workflow_cls.assert_called_once_with(
            llm_engine=mock_llm_engine,
            embedding_engine=mock_embedding_engine,
            vector_engine=mock_vector_cache,
        )
        mock_workflow_cls.return_value.execute.assert_awaited_once_with(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="EventID=4688 powershell.exe -enc ...",
        )
        assert result == expected_report
        assert (
            "[FORENSIC SERVICE] Initiating forensic analysis pipeline for 'windows'"
            in caplog.text
        )


async def test_analyze_and_report_translates_workflow_crash_into_http_500(
    mocker,
    mock_llm_engine: MagicMock,
    mock_embedding_engine: MagicMock,
    mock_vector_cache: MagicMock,
    caplog,
) -> None:
    """Error: logs diagnostic message and raises HTTP 500 when SocAgentWorkflow fails."""
    with caplog.at_level(logging.ERROR):
        mock_workflow_cls = mocker.patch(
            "src.api.services.forensic_service.SocAgentWorkflow"
        )
        mock_workflow_cls.return_value.execute = AsyncMock(
            side_effect=RuntimeError("Ollama inference timeout")
        )

        service = ForensicService(
            llm_engine=mock_llm_engine,
            embedding_engine=mock_embedding_engine,
            vector_engine=mock_vector_cache,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.analyze_and_report(
                platform=AvailablePlatforms.LINUX,
                raw_log="sudo cat /etc/shadow",
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert (
            "[FORENSIC SERVICE] AI Workflow collapsed: Ollama inference timeout"
            in caplog.text
        )
