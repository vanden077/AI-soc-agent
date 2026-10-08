from typing import Callable
from unittest.mock import MagicMock
import pytest

from langchain_ollama import ChatOllama
from pydantic_core import InitErrorDetails, ValidationError

from src.common.constants import Settings
from src.llm.engine import OllamaEngine
from soc_agent.schemas import SeverityLevel, RemediationAction
from soc_agent.schemas import EventAnalysis


def test_init_structured_model_properties(llm_engine: OllamaEngine, mock_settings: Settings):
    """Test that the private factory stores properties and binds ChatOllama correctly."""

    # 1. Check that instance variables are correctly mapped
    assert llm_engine.engine_name == "Ollama"
    assert llm_engine.model_name == mock_settings.LLM_MODEL
    assert llm_engine.base_url == mock_settings.LLM_URL
    assert llm_engine.temperature == mock_settings.LLM_TEMPERATURE

    # 2. Call the private factory method directly from our pre-packaged instance
    ollama = llm_engine._init_llm()

    # 3. Check ChatOllama instance is ready
    assert ollama is not None
    assert isinstance(ollama, ChatOllama)

def test_analyze_event_success(
    llm_engine: OllamaEngine,
    mock_llm_client: MagicMock,
    configure_llm_mock: Callable[..., MagicMock],
    valid_analysis_payload: dict,
    sample_prompt: list[tuple[str, str]],
):
    """Test standard nominal flow where the structured LLM returns a fully valid object synchronously."""
    expected_response = EventAnalysis(**valid_analysis_payload)

    mock_structured_pipeline = configure_llm_mock(return_value=expected_response)
    result = llm_engine.analyze_event(prompt=sample_prompt, response_schema=EventAnalysis)

    assert result is not None
    assert result.is_threat is True
    assert result.revised_severity == SeverityLevel.HIGH
    assert result.suggested_action == RemediationAction.ISOLATE_HOST
    mock_llm_client.with_structured_output.assert_called_once_with(EventAnalysis)
    mock_structured_pipeline.invoke.assert_called_once_with(sample_prompt)

def test_analyze_event_api_crash_raises_exception(
    llm_engine: OllamaEngine,
    mock_llm_client: MagicMock,
    configure_llm_mock: Callable[..., MagicMock],
    sample_prompt: list[tuple[str, str]],
):
    """Test that runtime API or connection crashes within Ollama are bubbled up properly."""
    configure_llm_mock(side_effect=Exception("Ollama socket connection refused"))

    with pytest.raises(Exception) as exc_info:
        llm_engine.analyze_event(prompt=sample_prompt, response_schema=EventAnalysis)
    assert "Ollama socket connection refused" in str(exc_info.value)

def test_analyze_event_validation_error_raises_exception(
    llm_engine: OllamaEngine,
    mock_llm_client: MagicMock,
    configure_llm_mock: Callable[..., MagicMock],
    sample_prompt: list[tuple[str, str]],
):
    """Test that a Pydantic ValidationError raised by the model client is propagated by the adapter."""

    line_errors: list[InitErrorDetails] = [
        {
            "type": "extra_forbidden",
            "loc": ("forbidden_llm_field",),
            "input": "malicious_payload",
        }
    ]

    # We construct a genuine Pydantic v2 ValidationError mapped to EventAnalysis
    # indicating that an extra forbidden field was found in the input data.
    configure_llm_mock(
        side_effect=ValidationError.from_exception_data(
            title="EventAnalysis",
            line_errors=line_errors
        )
    )

    with pytest.raises(ValidationError):
        llm_engine.analyze_event(prompt=sample_prompt, response_schema=EventAnalysis)