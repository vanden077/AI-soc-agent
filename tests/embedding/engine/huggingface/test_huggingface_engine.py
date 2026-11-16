from unittest.mock import patch

import pytest
from langchain_huggingface import HuggingFaceEmbeddings

from src.embedding.engine import HuggingFaceEngine
from src.constants import Settings



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

def test_huggingface_engine_embed_documents(embedding_engine: HuggingFaceEngine, mock_settings: Settings):
    """
    GIVEN a list of string payloads (STIX compiled contents)
    WHEN calling embed_documents to leverage bulk SIMD/AVX batching loops
    THEN verify it natively invokes embed_documents on the underlying LangChain layer.
    """
    texts_to_embed = ["malware payload text", "indicator payload text"]
    expected_matrix = [[0.1, 0.2], [0.3, 0.4]]

    with patch.object(HuggingFaceEmbeddings, "embed_documents", return_value=expected_matrix) as mock_embed:
        result = embedding_engine.embed_documents(texts=texts_to_embed)
        assert result == expected_matrix
        mock_embed.assert_called_once_with(texts=texts_to_embed)

def test_huggingface_engine_embed_documents_raises_exception(embedding_engine: HuggingFaceEngine, mock_settings: Settings):
    """
    GIVEN a list of string payloads causing an engine exhaustion or failure
    WHEN calling embed_documents and an exception occurs in the native layer
    THEN verify that the exception is bubbled up immediately without being swallowed.
    """
    texts_to_embed = ["malicious chunk 1", "malicious chunk 2"]

    with patch.object(
            HuggingFaceEmbeddings, "embed_documents",
            side_effect=RuntimeError("CPU Thread Allocation Failed")
    ) as mock_embed:
        with pytest.raises(RuntimeError) as exc_info:
            embedding_engine.embed_documents(texts=texts_to_embed)

        assert "CPU Thread Allocation Failed" in str(exc_info.value)
        mock_embed.assert_called_once_with(texts=texts_to_embed)
