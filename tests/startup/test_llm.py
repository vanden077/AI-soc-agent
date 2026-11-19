import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.schemas import AvailablePlatforms
from src.constants import Settings
from src.llm.interfaces import ILlmEngine
from src.startup.llm import init_llm, warmup_llm_background


def test_init_llm_nominal_instantiates_manager_and_returns_engine(
        mocker,
        mock_settings,
        caplog,
) -> None:
    """Nominal: instantiates LlmManager with settings attributes and returns its engine."""
    with caplog.at_level(logging.INFO):
        mock_engine: MagicMock = mocker.MagicMock(spec=ILlmEngine)
        mock_manager_cls = mocker.patch("src.startup.llm.LlmManager")
        mock_manager_cls.return_value.engine = mock_engine

        result = init_llm(settings=mock_settings)

        mock_manager_cls.assert_called_once_with(
            base_url=mock_settings.LLM_URL,
            llm_engine=mock_settings.LLM_ENGINE,
            llm_model=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE,
        )
        assert result is mock_engine
        assert (
                f"[LLM STARTUP] Load LLM {mock_settings.LLM_ENGINE}, model {mock_settings.LLM_MODEL}..."
                in caplog.text
        )


def test_init_llm_logs_and_reraises_on_exception(
        mocker,
        caplog,
) -> None:
    """Error: logs diagnostic message and re-raises exception when LlmManager fails."""
    with caplog.at_level(logging.ERROR):
        mock_settings = mocker.MagicMock(spec=Settings)
        mock_settings.LLM_URL = "http://localhost:11434"
        mock_settings.LLM_ENGINE = "invalid_engine"
        mock_settings.LLM_MODEL = "llama3.1:8b"
        mock_settings.LLM_TEMPERATURE = 0.0

        mock_manager_cls = mocker.patch("src.startup.llm.LlmManager")
        mock_manager_cls.side_effect = ValueError(
            "Engine 'invalid_engine' not supported"
        )

        with pytest.raises(ValueError, match="Engine 'invalid_engine' not supported"):
            init_llm(settings=mock_settings)

        assert (
                "[LLM STARTUP] LLM initialization failed because: Engine 'invalid_engine' not supported"
                in caplog.text
        )


@pytest.mark.asyncio
async def test_warmup_llm_background_nominal_executes_probe(
        mocker,
        caplog,
) -> None:
    """Nominal: schedules background ForensicService probe and logs readiness."""
    mock_llm = MagicMock()
    mock_embedding = MagicMock()
    mock_vector = MagicMock()
    mock_forensic_cls = mocker.patch("src.startup.llm.ForensicService")
    mock_forensic_cls.return_value.analyze_and_report = AsyncMock(return_value=None)

    with caplog.at_level(logging.INFO):
        task = warmup_llm_background(
            llm_engine=mock_llm,
            embedding_engine=mock_embedding,
            vector_engine=mock_vector,
        )
        assert isinstance(task, asyncio.Task)
        await task

    mock_forensic_cls.assert_called_once_with(
        llm_engine=mock_llm,
        embedding_engine=mock_embedding,
        vector_engine=mock_vector,
    )
    mock_forensic_cls.return_value.analyze_and_report.assert_awaited_once_with(
        platform=AvailablePlatforms.LINUX,
        raw_log='sshd[1]: Accepted publickey for root from 127.0.0.1 port 22 ssh2',
    )
    assert "[LLM WARMUP] AI forensic pipeline is warm and ready." in caplog.messages


@pytest.mark.asyncio
async def test_warmup_llm_background_logs_warning_on_failure(
        mocker,
        caplog,
) -> None:
    """Error: catches warmup exceptions without crashing the background task."""
    mock_forensic_cls = mocker.patch("src.startup.llm.ForensicService")
    mock_forensic_cls.return_value.analyze_and_report = AsyncMock(
        side_effect=RuntimeError("Ollama cold start error")
    )

    with caplog.at_level(logging.WARNING):
        task = warmup_llm_background(
            llm_engine=MagicMock(),
            embedding_engine=MagicMock(),
            vector_engine=MagicMock(),
        )
        await task

    assert (
            "[LLM WARMUP] Background warmup probe failed: Ollama cold start error"
            in caplog.messages
    )
