from unittest.mock import MagicMock, patch

import pytest

from src.common.constants import Settings
from src.llm.engine import OllamaEngine
from src.llm.models import SiemAlertState
from src.llm.schemas import SeverityLevel, RemediationAction


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
def sample_cyber_state() -> SiemAlertState:
    """Provide a valid mock instance of SiemAlertState matching Python 3.13 modern TypedDict."""
    return {
        "raw_alert": {
            "event_id": 999,
            "source": "siem_rdp_logs",
            "message": "Multiple failed authentication attempts detected",
        },
        "correlated_logs": [
            {
                "timestamp": "2026-09-10T14:32:00Z",
                "src_ip": "192.168.1.50",
                "status": "failure",
            }
        ],
        "analysis": None,  # Strictly compliant with EventAnalysis | None union contract
        "metadata": {"ingestion_engine": "wazuh", "analyst_group": "tier_1"},
    }
