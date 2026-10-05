from unittest.mock import patch

import pytest
from langchain_huggingface import HuggingFaceEmbeddings
from src.embedding.engine.huggingface_engine import HuggingFaceEngine


def test_huggingface_engine_init():
    """Test hugging face embedding init"""
    model_name = "all-MiniLM-L6-v2"

    # patch preventing heavy checks, 2ms instead of 19 seconds without altering behavior
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None) as mock_init:

        huggingface = HuggingFaceEngine(model_name=model_name)
        mock_init.assert_called_once_with(model_name=model_name)
        assert huggingface.model_name == model_name
        assert huggingface.engine_name == "huggingface"
        assert isinstance(huggingface.embedding, HuggingFaceEmbeddings)


def test_huggingface_engine_embed_query():
    """Test hugging face embedding embed query"""
    model_name = "all-MiniLM-L6-v2"
    text_to_embed = "test"
    expected_vector = [0.1, 0.2, 0.3, 0.4]

    # patch preventing heavy checks, 2ms instead of 19 seconds without altering behavior
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None) as mock_init:
        huggingface = HuggingFaceEngine(model_name=model_name)
        mock_init.assert_called_once_with(model_name=model_name)

        with patch.object(HuggingFaceEmbeddings, "embed_query", return_value=expected_vector) as mock_embed:
            result = huggingface.embed_query(text=text_to_embed)
            assert result == expected_vector
            mock_embed.assert_called_once_with(text=text_to_embed)


def test_huggingface_engine_embed_query_raises_exception():
    """Test hugging face embedding crash will propagate exception"""
    model_name = "all-MiniLM-L6-v2"
    text_to_embed = "im gonna crash without any reasons"

    # patch preventing heavy checks, 2ms instead of 19 seconds without altering behavior
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None) as mock_init:
        with patch.object(HuggingFaceEmbeddings, "embed_query",
                          side_effect=RuntimeError("CUDA Out of Memory")) as mock_embed:
            huggingface = HuggingFaceEngine(model_name=model_name)
            with pytest.raises(RuntimeError) as exc_info:
                huggingface.embed_query(text=text_to_embed)
                mock_init.assert_called_once_with(model_name=model_name)

            assert "CUDA Out of Memory" in str(exc_info.value)
            mock_embed.assert_called_once_with(text=text_to_embed)