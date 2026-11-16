from typing import Any, Type
from unittest.mock import MagicMock

import pytest

from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine


class DummyEmbeddingEngine(IEmbeddingEngine[MagicMock]):
    """Backend-agnostic stub implementing IEmbeddingEngine for manager contract testing."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._embedding = self._init_embedding()

    def _init_embedding(self) -> MagicMock:
        return MagicMock()

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_documents(self, texts: list[str]) -> list[list[float]] | Any:
        raise NotImplementedError

    @property
    def engine_name(self) -> str:
        return "Dummy"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def embedding(self) -> MagicMock:
        return self._embedding


@pytest.fixture
def dummy_embedding_engine_cls() -> Type[DummyEmbeddingEngine]:
    """Expose the backend-agnostic IEmbeddingEngine implementation class."""
    return DummyEmbeddingEngine