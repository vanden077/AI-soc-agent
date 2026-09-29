from unittest.mock import MagicMock

import pytest
from langchain_core.runnables import RunnableSequence
from pydantic import ValidationError
from pydantic_core import InitErrorDetails

from src.adapters.llm import OllamaAdapter
from src.models.siem_alert_state import SiemAlertState
from schemas.llm.event_analysis import EventAnalysis, RemediationAction, SeverityLevel


def test_init_structured_model_properties(llm_adapter: OllamaAdapter) -> None:
    """Test that the private factory stores properties and binds EventAnalysis correctly using the conftest fixture."""

    # 1. Check that instance variables are correctly mapped and persisted in our fixture
    assert llm_adapter.model_name == "llama3.1:latest"
    assert llm_adapter.base_url == "http://localhost:11434"

    # 2. Call the private factory method directly from our pre-packaged instance
    runnable = llm_adapter._init_structured_model()

    # 3. Verify that the contract is alive and successfully mapped our validation schema
    assert runnable is not None
    assert isinstance(runnable, RunnableSequence)
    output_schema = runnable.get_output_schema()
    assert output_schema == EventAnalysis


def test_format_messages_structures_prompt_correctly(
    sample_cyber_state: SiemAlertState,
) -> None:
    """Test that the static helper formats state parameters into explicit System and Human messages."""
    # Execute the static method directly from the class namespace using our fixture
    messages = OllamaAdapter._format_messages(state=sample_cyber_state)
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert isinstance(messages[0], tuple)
    assert isinstance(messages[1], tuple)
    assert messages[0][0] == "system"
    assert len(messages[0][1]) > 0
    assert messages[1][0] == "user"
    assert len(messages[1][1]) > 0


def test_analyze_event_success(
    llm_adapter: OllamaAdapter,
    mock_llm_client: MagicMock,
    valid_analysis_payload: dict,
    sample_cyber_state: SiemAlertState,
) -> None:
    """Test standard nominal flow where the structured LLM returns a fully valid object synchronously."""
    expected_response = EventAnalysis(**valid_analysis_payload)

    # Using side_effect as a lambda forces the mock to return expected_response
    # regardless of how input/arguments are passed to the .invoke() method
    mock_llm_client.invoke.side_effect = lambda *args, **kwargs: expected_response

    result = llm_adapter.analyze_event(state=sample_cyber_state)

    assert result is not None
    assert result.is_threat is True
    assert result.revised_severity == SeverityLevel.HIGH
    assert result.suggested_action == RemediationAction.ISOLATE_HOST
    mock_llm_client.invoke.assert_called_once()


def test_analyze_event_api_crash_raises_exception(
    llm_adapter: OllamaAdapter,
    mock_llm_client: MagicMock,
    sample_cyber_state: SiemAlertState,
) -> None:
    """Test that runtime API or connection crashes within Ollama are bubbled up properly."""
    mock_llm_client.invoke.side_effect = Exception("Ollama socket connection refused")

    with pytest.raises(Exception) as exc_info:
        llm_adapter.analyze_event(state=sample_cyber_state)

    assert "Ollama socket connection refused" in str(exc_info.value)


def test_analyze_event_validation_error_raises_exception(
    llm_adapter: OllamaAdapter,
    mock_llm_client: MagicMock,
    sample_cyber_state: SiemAlertState,
) -> None:
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
    mock_llm_client.invoke.side_effect = ValidationError.from_exception_data(
        title="EventAnalysis", line_errors=line_errors
    )

    # We ensure that your adapter's 'except ValidationError as ve:' block is reached and re-raises it.
    with pytest.raises(ValidationError):
        llm_adapter.analyze_event(state=sample_cyber_state)
