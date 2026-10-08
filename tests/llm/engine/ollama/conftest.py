from typing import Callable, Any
from unittest.mock import MagicMock, patch

import pytest

from src.common.constants import Settings
from src.llm.engine import OllamaEngine
from soc_agent.models import SiemAlertState
from soc_agent.schemas import SeverityLevel, RemediationAction


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Provide a mocked instance of the structured LLM runner."""
    # This mock represents self.structured_llm directly
    mock_runner = MagicMock()
    return mock_runner


@pytest.fixture
def llm_engine(mock_llm_client: MagicMock, mock_settings: Settings) -> OllamaEngine:
    """Initialize OllamaEngine by mocking its internal structured model initialization."""
    # Patch the private method to return our mock runner directly, bypassing HTTPX calls entirely
    with patch.object(
        OllamaEngine, "_init_llm", return_value=mock_llm_client
    ):
        return OllamaEngine(
            base_url=mock_settings.LLM_URL,
            model_name=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE
        )


@pytest.fixture
def configure_llm_mock(mock_llm_client: MagicMock) -> Callable[..., MagicMock]:
    """
    Factory fixture to dynamically configure the chained LangChain mock
    (with_structured_output().invoke) without repeating the boilerplate.

    Allows setting either a fixed 'return_value' or a dynamic 'side_effect'.
    """
    def _configure(return_value: Any = None, side_effect: Any = None) -> MagicMock:
        # create mock of LangChain RunnableSequence
        mock_structured_pipeline = MagicMock()

        if side_effect is not None:
            mock_structured_pipeline.invoke.side_effect = side_effect
        else:
            mock_structured_pipeline.invoke.return_value = return_value

        # Link LangChain mock with the call to structured_output to return the sequence
        mock_llm_client.with_structured_output.return_value = mock_structured_pipeline
        return mock_structured_pipeline
    return _configure

@pytest.fixture
def valid_analysis_payload() -> dict:
    """Provide a raw payload strictly matching EventAnalysis fields and Enum constraints."""
    return {
        "is_threat": True,
        "revised_severity": SeverityLevel.HIGH,
        "justification": "Brute force attack detected via repetitive RDP failures in security logs.",
        "mitre_correlations": [
            {
                "tactic": "Credential Access",
                "technic_id": "T1110.001",
                "technic_name": "Brute Force: Password Guessing",
                "confidence_score": 5,
            }
        ],
        "suggested_action": RemediationAction.ISOLATE_HOST,
    }


@pytest.fixture
def sample_prompt() -> list[tuple[str, str]]:
    """Provide a valid mock instance of SiemAlertState matching Python 3.13 modern TypedDict."""
    system_prompt = (
        "You are a senior SOC analyst and expert threat hunter.\n"
        "Analyze the provided SIEM alert and correlated logs to produce a strictly structured event analysis.\n\n"
        "Mandatory rules:\n"
        "1. Rely only on clear facts from the input data.\n"
        "2. Fill every required field in the analysis schema.\n"
        "3. Do not invent extra fields (the output schema forbids unknown properties)."
    )

    siem_alert = SiemAlertState(
        raw_alert={
            "event_id": 999,
            "source": "siem_rdp_logs",
            "message": "Multiple failed authentication attempts detected",
        },
        correlated_logs=[
            {
                "timestamp": "2026-09-10T14:32:00Z",
                "src_ip": "192.168.1.50",
                "status": "failure",
            }
        ],
        analysis=None,
        metadata={"ingestion_engine": "wazuh", "analyst_group": "tier_1"}
    )

    user_content = (
        f"--- INITIAL SIEM ALERT ---\n{siem_alert['raw_alert']}\n\n"
        f"--- SELECTED CORRELATED LOGS ---\n{siem_alert['correlated_logs']}"
    )

    return [("system", system_prompt), ("user", user_content)]



