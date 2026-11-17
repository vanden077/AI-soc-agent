from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis, FakeServer
from redisvl.index import SearchIndex
from redisvl.schema import IndexSchema
from src.persistence.engine.redis.driver.redis_driver import RedisDriver


@pytest.fixture(scope="function", autouse=True)
def mock_redis_driver(mocker: Any) -> MagicMock:
    """
    Global fixture replacing Redis instance by FakeRedis.
    Simulates ONE single Redis server (FakeServer) for the test.
    The clients (JSON and Vector) will be completely isolated via their
    respective connection pools and logical 'db' indexes.
    """
    single_redis_server = FakeServer()

    def _shared_server_factory(*args: Any, **kwargs: Any) -> FakeRedis:
        kwargs["server"] = single_redis_server
        kwargs.pop("protocol", None)
        kwargs.pop("username", None)
        kwargs.pop("password", None)
        return FakeRedis(*args, **kwargs)

    return mocker.patch(
        "src.persistence.engine.redis.driver.redis_driver.Redis",
        side_effect=_shared_server_factory,
    )


@pytest.fixture
def redis_driver_factory() -> Callable[..., RedisDriver]:
    """
    Factory fixture providing a clean, lazy-loaded concrete RedisDriver instance.
    Allows tests to control the exact timing of instantiation.
    """

    def _create_driver(**kwargs: Any) -> RedisDriver:
        default_params: dict[str, Any] = {
            "host": "test",
            "port": 1,
            "username": "username",
            "password": "test",
            "max_size_pool": 1,
            "retry_strategy": 1,
        }
        default_params.update(kwargs)
        return RedisDriver(**default_params)

    return _create_driver


@pytest.fixture
def mock_redis_vl_search_index(mocker: Any) -> MagicMock:
    """
    Mock nested structure of a RedisVL SearchIndex aligned with `schema.model_dump(mode="json")`.
    """
    mock_index = MagicMock(spec=SearchIndex)
    mock_schema = MagicMock(spec=IndexSchema)
    mock_index.schema = mock_schema

    mock_index.name = "agnostic_production_index"
    mock_index.exists.return_value = False
    mock_index.create.return_value = None

    mock_index_config = MagicMock()
    mock_index_config.prefix = "mitre"
    mock_schema.index = mock_index_config

    schema_dump_payload: dict[str, Any] = {
        "fields": {
            "id": {"type": "tag"},
            "raw_content": {"type": "text"},
            "text_embedding": {
                "type": "vector",
                "path": "$.payload.text_embedding",
                "attrs": {
                    "dims": 384,
                    "distance_metric": "cosine",
                    "algorithm": "hnsw",
                },
            },
            "image_embedding": {
                "type": "vector",
                "path": "$.payload.image_embedding",
                "attrs": {
                    "dims": 384,
                    "distance_metric": "l2",
                    "algorithm": "flat",
                },
            },
        }
    }
    mock_schema.model_dump.return_value = schema_dump_payload

    mocker.patch.object(SearchIndex, "from_yaml", return_value=mock_index)
    return mock_index
