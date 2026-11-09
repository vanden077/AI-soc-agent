from typing import Any
from unittest.mock import MagicMock
import pytest
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine

class FakeRedisDocument:
    """Simulate a fake document returned by Redis vl"""
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        self.id = kwargs.get("id", "unknown_key")

    @property
    def vector_distance(self) -> Any:
        return self.__dict__.get("vector_distance")


@pytest.fixture(scope="function")
def redis_doc_factory():
    """Factory fixture creating raw Redis database documents to isolate parser tests.

    Allows tests to easily inject dynamic payloads, metadata fields, and custom distances
    without triggering lower-level network or library parsing layers.
    """
    def _create_documents(records: list[dict[str, Any]]) -> list[FakeRedisDocument]:
        return [FakeRedisDocument(**record) for record in records]

    return _create_documents


@pytest.fixture(scope="function")
def mock_embedding_engine() -> MagicMock:
    """
    Isolate the covariant embedding engine.
    Optimized to the minimal dimension of 384 to maximize test runtime execution.
    """
    engine = MagicMock(spec=IEmbeddingEngine)
    engine.embed_query.return_value = [0.1] * 384
    return engine
