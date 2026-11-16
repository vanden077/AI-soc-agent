from unittest.mock import patch

import pytest
from langchain_huggingface import HuggingFaceEmbeddings

from src.embedding.engine import HuggingFaceEngine
from src.constants import Settings

@pytest.fixture
def embedding_engine(mock_settings: Settings) -> HuggingFaceEngine:
    """Initialize HuggingFace engine by mocking its internal structured model initialization."""
    # patch preventing heavy checks, 2ms instead of 19 seconds without altering behavior
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None):
        return HuggingFaceEngine(model_name=mock_settings.EMBEDDING_MODEL_NAME)
