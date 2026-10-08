import pytest

from src.llm.interfaces.llm_provider import LlmProvider


def test_embedding_provider_contains_expected_engines():
    """Check implemented engines are present"""
    assert LlmProvider.OLLAMA == "ollama"


def test_embedding_provider_raises_value_error_for_invalid_string():
    """Check an unknown engine raises ValueError"""
    with pytest.raises(ValueError):
        LlmProvider("unknown-engine")