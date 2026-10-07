from unittest.mock import patch

import pytest
from langchain_huggingface import HuggingFaceEmbeddings

from embedding.engine import HuggingFaceEngine
from src.common.constants import Settings
from src.embedding.embedding_manager import EmbeddingManager



def test_embedding_manager_initializes_huggingface_successfully(mock_settings: Settings):
    """
    Check manager return an instance of HuggingFaceEngine encapsulating an instance of HuggingFaceEmbeddings
    """
    # patch preventing heavy checks, 2ms instead of 19 seconds without altering behavior
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None) as mock_init:
        embedding_manager = EmbeddingManager(
            provider=mock_settings.EMBEDDING_ENGINE,
            model_name=mock_settings.EMBEDDING_MODEL_NAME
        )
        mock_init.assert_called_once_with(model_name=mock_settings.EMBEDDING_MODEL_NAME)

        # check we have access to HuggingFaceEngine
        assert isinstance(embedding_manager.engine, HuggingFaceEngine)

        # check everything is successfully sent through the embedding engine
        assert embedding_manager.engine.model_name == mock_settings.EMBEDDING_MODEL_NAME
        assert embedding_manager.engine.engine_name == mock_settings.EMBEDDING_ENGINE
        # check we have access to HuggingFaceEmbeddings
        assert isinstance(embedding_manager.engine.embedding, HuggingFaceEmbeddings)


def test_embedding_manager_raises_value_error_for_unknown_provider(mock_settings: Settings):
    """Check manager raises exception if the provider isn't supported"""
    invalid_provider = "invalid-provider-name"

    with pytest.raises(ValueError) as exc_info:
        EmbeddingManager(provider=invalid_provider, model_name=mock_settings.EMBEDDING_MODEL_NAME)

    assert f"Engine '{invalid_provider}' not supported" in str(exc_info.value)


def test_embedding_manager_raises_not_implemented_error_for_unhandled_enum_value(mock_settings: Settings):
    """Check a valid Enum but not yet implemented engine will raise an exception
    into the "_" case of _check_embedding_provider_availability function."""
    provider = "openai"

    # Patch EmbeddingProvider inside the manager module to simulate 'openai' as a valid entry
    with patch("src.embedding.embedding_manager.EmbeddingProvider") as mock_enum:
        # Trick the try/except block to accept 'openai' and return it for the match-case statement
        mock_enum.return_value = "openai"
        with pytest.raises(NotImplementedError) as exc_info:
            EmbeddingManager(provider=provider, model_name=mock_settings.EMBEDDING_MODEL_NAME)

        assert f"Engine 'openai' is listed but not yet implemented" in str(exc_info.value)
