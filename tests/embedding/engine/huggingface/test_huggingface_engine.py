from unittest.mock import patch

import pytest
from langchain_huggingface import HuggingFaceEmbeddings

from src.embedding.engine import HuggingFaceEngine
from src.common.constants import Settings



def test_huggingface_engine_init(embedding_engine: HuggingFaceEngine, mock_settings: Settings):
    """Test hugging face embedding init"""
    assert embedding_engine.model_name == mock_settings.EMBEDDING_MODEL_NAME
    assert embedding_engine.engine_name == mock_settings.EMBEDDING_ENGINE
    assert isinstance(embedding_engine.embedding, HuggingFaceEmbeddings)


def test_huggingface_engine_embed_query(embedding_engine: HuggingFaceEngine, mock_settings: Settings):
    """Test hugging face embedding query"""
    text_to_embed = "test"
    expected_vector = [0.1, 0.2, 0.3, 0.4]

    with patch.object(HuggingFaceEmbeddings, "embed_query", return_value=expected_vector) as mock_embed:
        result = embedding_engine.embed_query(text=text_to_embed)
        assert result == expected_vector
        mock_embed.assert_called_once_with(text=text_to_embed)


def test_huggingface_engine_embed_query_raises_exception(embedding_engine: HuggingFaceEngine, mock_settings: Settings):
    """Test hugging face embedding crash will propagate exception"""
    text_to_embed = "im gonna crash without any reasons"

    with patch.object(
            HuggingFaceEmbeddings, "embed_query",
            side_effect=RuntimeError("CUDA Out of Memory")
    ) as mock_embed:
            with pytest.raises(RuntimeError) as exc_info:
                embedding_engine.embed_query(text=text_to_embed)

            assert "CUDA Out of Memory" in str(exc_info.value)
            mock_embed.assert_called_once_with(text=text_to_embed)