from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fakeredis import FakeServer, FakeRedis
from redisvl.index import SearchIndex
from redisvl.schema import IndexSchema

from src.common.cache.driver.redis_driver import RedisDriver


@pytest.fixture(scope="function", autouse=True)
def mock_redis_driver(mocker):
    """
    Global fixture replacing Redis instance by FakeRedis.
    Simulates ONE single Redis server (FakeServer) for the test.
    The clients (JSON and Vector) will be completely isolated via their
    respective connection pools and logical 'db' indexes.
    """
    single_redis_server = FakeServer()

    def _shared_server_factory(*args, **kwargs):
        # each client will be connected to this server, but through isolated connexions pools.
        kwargs["server"] = single_redis_server
        return FakeRedis(*args, **kwargs)

    return mocker.patch(
        "src.common.cache.driver.redis_driver.Redis",
        side_effect=_shared_server_factory
    )

class FakeRedisClient(RedisDriver):
    """Fake client doing nothing except inheriting driver"""


@pytest.fixture
def redis_driver_factory():
    """
    Factory fixture providing a clean, lazy-loaded driver instance.
    Allows tests to control the exact timing of instantiation.
    """
    def _create_driver(**kwargs):
        # Default mandatory configuration parameters
        default_params = {
            "host": "test",
            "port": 1,
            "username": "username",
            "password": "test",
            "max_size_pool": 1,
            "retry_strategy": 1,
        }
        # Allow tests to override parameters if needed
        default_params.update(kwargs)
        return FakeRedisClient(**default_params)

    return _create_driver


@pytest.fixture
def mock_redis_vl_search_index(mocker):
    """
    Mock nested structure of a RedisVL index.
    A RedisVL index owns a SearchIndex, and the SearchIndex owns an IndexSchema.

    index.schema.fields owns the entire structure
    index.schema.vector_fields owns only vectors extracted from index.schema.fields
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

    # Non vector metadata
    field_id = MagicMock()  # could be a tag or an id
    field_id.type = "tag"
    field_content = MagicMock()  # could be a text
    field_content.type = "text"

    # Simulate vectors spaces
    field_text_vec = MagicMock()
    field_text_vec.type = "vector"
    field_text_vec.dimension = 384
    field_text_vec.metric = "cosine"
    field_text_vec.algorithm = "hnsw"
    field_text_vec.path = "$.payload.text_embedding"

    field_image_vec = MagicMock()
    field_image_vec.type = "vector"
    field_image_vec.dimension = 384
    field_image_vec.metric = "l2"
    field_image_vec.algorithm = "flat"
    field_image_vec.path = "$.payload.image_embedding"

    # .fields owns the entire structure
    fields_dict = {
        "id": field_id,
        "raw_content": field_content,
        "text_embedding": field_text_vec,
        "image_embedding": field_image_vec
    }

    # .vector_fields owns only vectors extracted from .fields
    vector_dict = {
        "text_embedding": field_text_vec,
        "image_embedding": field_image_vec
    }

    type(mock_schema).fields = PropertyMock(return_value=fields_dict)
    type(mock_schema).vector_fields = PropertyMock(return_value=vector_dict)

    mocker.patch.object(SearchIndex, "from_yaml", return_value=mock_index)

    return mock_index