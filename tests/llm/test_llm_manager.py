from unittest.mock import patch, MagicMock

import pytest

from src.common.constants import Settings
from src.llm.llm_manager import LlmManager
from src.llm.engine import OllamaEngine


def test_llm_manager_initializes_ollama_successfully(mock_settings: Settings):
    """
    Check manager return an instance of OllamaEngine encapsulating an instance of ChatOllama
    """
    # patch preventing heavy llm loading, here we are just testing that the factory provides a valid instance
    with patch.object(OllamaEngine, "_init_llm", return_value=MagicMock()):
        llm = LlmManager(
            base_url=mock_settings.LLM_URL,
            llm_engine=mock_settings.LLM_ENGINE,
            llm_model=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE
        )

        assert isinstance(llm.engine, OllamaEngine)
        assert llm.engine.base_url == mock_settings.LLM_URL
        assert llm.engine.model_name == mock_settings.LLM_MODEL
        assert llm.engine.temperature == mock_settings.LLM_TEMPERATURE


def test_llm_manager_raises_value_error_for_unknown_provider(mock_settings: Settings):
    """Check manager raises exception if the provider isn't supported"""
    invalid_llm_engine = "unknown_engine"

    with pytest.raises(ValueError) as exc_info:
        LlmManager(
            base_url=mock_settings.LLM_URL,
            llm_engine=invalid_llm_engine,
            llm_model=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE
        )

    assert f"Engine '{invalid_llm_engine}' not supported" in str(exc_info.value)

def test_llm_manager_raises_not_implemented_error_for_unhandled_enum_value(mock_settings: Settings):
    """Check a valid Enum but not yet implemented engine will raise an exception
    into the "_" case of _check_llm_provider_availability function."""
    llm_engine = "mistral"

    # Patch LlmProvider inside the manager module to simulate 'mistral' as a valid entry
    with patch("src.llm.llm_manager.LlmProvider") as mock_enum:
        # Trick the try/except block to accept 'openai' and return it for the match-case statement
        mock_enum.return_value = llm_engine
        with pytest.raises(NotImplementedError) as exc_info:
            LlmManager(
                base_url=mock_settings.LLM_URL,
                llm_engine=llm_engine,
                llm_model=mock_settings.LLM_MODEL,
                temperature=mock_settings.LLM_TEMPERATURE
            )

        assert f"Engine 'mistral' is listed but not yet implemented" in str(exc_info.value)