import logging
from unittest.mock import MagicMock

import pytest
from src.constants import Settings
from src.llm.interfaces import ILlmEngine
from src.startup.llm import init_llm


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
