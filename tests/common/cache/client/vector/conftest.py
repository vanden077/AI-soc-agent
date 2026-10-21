from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from src.common.cache.driver.redis_driver import RedisDriver
from src.common.cache import VectorCacheClient
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


@pytest.fixture(scope="function")
def vector_cache(mock_redis_driver, mock_embedding_engine, mock_redis_vl_search_index: MagicMock):
    """
    Instantiate VectorCacheClient in its raw, nominal post-construction state.
    Pre-patches only the inherited parent search_index property to route queries to the mock index.
    The cache client is yield with a valid vector fields catalog (see mock_redis_vl_search_index from cache.conftest)
    """
    vector_client = VectorCacheClient(
        host="test",
        port=1,
        username="username",
        password="test",
        max_size_pool=1,
        retry_strategy=1,
        decode_responses=False,
        ssl=False,
        db=1,
        embedding_engine=mock_embedding_engine,
        index_name="mitre_attack_v1"
    )
    vector_client.init_pool()

    # We ONLY bridge the parent index descriptor property.
    # No lifespans routines or catalog logic are triggered here.
    with patch.object(
        RedisDriver,
        "search_index",
        new_callable=PropertyMock,
        return_value=mock_redis_vl_search_index
    ):
        yield vector_client