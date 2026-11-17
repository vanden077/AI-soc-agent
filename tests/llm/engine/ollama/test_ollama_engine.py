from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from langchain_ollama import ChatOllama
from pydantic import ValidationError
from pydantic_core import InitErrorDetails
from src.constants import Settings
from src.llm.engine import OllamaEngine

from tests.llm.engine.conftest import DummyStructuredOutput


def test_init_structured_model_properties(
    llm_engine: OllamaEngine, mock_settings: Settings
) -> None:
    """Verify OllamaEngine properties and native ChatOllama instantiation."""
    assert llm_engine.engine_name == "Ollama"
    assert llm_engine.model_name == mock_settings.LLM_MODEL
    assert llm_engine.base_url == mock_settings.LLM_URL
    assert llm_engine.temperature == mock_settings.LLM_TEMPERATURE

    ollama = llm_engine._init_llm()
    assert isinstance(ollama, ChatOllama)


def test_analyze_event_success(
    llm_engine: OllamaEngine,
    mock_llm_client: MagicMock,
    configure_llm_mock: Callable[..., MagicMock],
    sample_prompt: list[tuple[str, str]],
) -> None:
    """Verify nominal structured output parsing via LangChain runner."""
    expected_response = DummyStructuredOutput(
        is_threat=True, summary="Encoded PowerShell command"
    )
    mock_structured_pipeline = configure_llm_mock(return_value=expected_response)

    result = llm_engine.analyze_event(
        prompt=sample_prompt, response_schema=DummyStructuredOutput
    )

    assert result == expected_response
    assert result.is_threat is True
    assert result.summary == "Encoded PowerShell command"
    mock_llm_client.with_structured_output.assert_called_once_with(
        DummyStructuredOutput
    )
    mock_structured_pipeline.invoke.assert_called_once_with(sample_prompt)


def test_analyze_event_api_crash_raises_exception(
    llm_engine: OllamaEngine,
    configure_llm_mock: Callable[..., MagicMock],
    sample_prompt: list[tuple[str, str]],
) -> None:
    """Verify connection or runtime API failures are logged and propagated."""
    configure_llm_mock(side_effect=RuntimeError("Ollama socket connection refused"))

    with pytest.raises(RuntimeError, match="Ollama socket connection refused"):
        llm_engine.analyze_event(
            prompt=sample_prompt, response_schema=DummyStructuredOutput
        )


def test_analyze_event_validation_error_raises_exception(
    llm_engine: OllamaEngine,
    configure_llm_mock: Callable[..., MagicMock],
    sample_prompt: list[tuple[str, str]],
) -> None:
    """Verify Pydantic ValidationError raised on malformed LLM output is propagated."""
    line_errors: list[InitErrorDetails] = [
        {
            "type": "extra_forbidden",
            "loc": ("forbidden_llm_field",),
            "input": "malicious_payload",
        }
    ]
    configure_llm_mock(
        side_effect=ValidationError.from_exception_data(
            title="_DummyStructuredOutput",
            line_errors=line_errors,
        )
    )

    with pytest.raises(ValidationError):
        llm_engine.analyze_event(
            prompt=sample_prompt, response_schema=DummyStructuredOutput
        )
