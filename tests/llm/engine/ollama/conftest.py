from typing import Callable, Any
from unittest.mock import MagicMock, patch

import pytest

from src.constants import Settings
from src.llm.engine import OllamaEngine


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
