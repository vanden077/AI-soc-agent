from unittest.mock import MagicMock

import pytest

from src.persistence.engine.redis.client.json.json_cache_client import JsonCacheClient
from src.persistence.engine.redis.client.vector.ingestion_cache_client import IngestionCacheClient
from src.persistence.engine.redis.client.vector.vector_cache_client import VectorCacheClient
from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.engine.redis.redis_factory.redis_factory import RedisPersistenceFactory


def test_create_json_engine_initializes_resp3_client(mocker, redis_driver_factory) -> None:
    """Nominal: instantiates JsonCacheClient with an initialized RESP3 driver (vector_capability=False)."""
    mocker.patch("src.persistence.engine.redis.redis_factory.redis_factory.RedisDriver", side_effect=redis_driver_factory)
    factory = RedisPersistenceFactory()

    client = factory.create_json_engine(db=0, decode_responses=True, ssl=False)

    assert isinstance(client, JsonCacheClient)
    assert client._driver._vector_capability is False
    assert client._driver._client is not None


def test_create_vector_search_engine_nominal(
    mocker, redis_driver_factory, mock_redis_vl_search_index: MagicMock
) -> None:
    """Nominal: instantiates VectorCacheClient with RESP2 driver and synchronizes lifespan catalog."""
    mocker.patch("src.persistence.engine.redis.redis_factory.redis_factory.RedisDriver", side_effect=redis_driver_factory)
    mock_redis_vl_search_index.exists.return_value = True
    factory = RedisPersistenceFactory()

    client = factory.create_vector_search_engine(
        index_path="/schemas/mitre.yaml",
        db=1,
        decode_responses=False,
        ssl=False,
    )

    assert isinstance(client, VectorCacheClient)
    assert client._driver._vector_capability is True
    assert client._driver._client is not None
    mock_redis_vl_search_index.exists.assert_called_once()


def test_create_vector_search_engine_closes_driver_on_catalog_failure(
    mocker, redis_driver_factory, mock_redis_vl_search_index: MagicMock
) -> None:
    """Rollback: closes driver connection pool and re-raises if catalog synchronization fails."""
    mocker.patch("src.persistence.engine.redis.redis_factory.redis_factory.RedisDriver", side_effect=redis_driver_factory)
    spy_close = mocker.spy(RedisDriver, "close")
    mocker.patch.object(
        VectorCacheClient,
        "sync_lifespan_catalog",
        side_effect=RuntimeError("Catalog synchronization failed"),
    )
    factory = RedisPersistenceFactory()

    with pytest.raises(RuntimeError, match="Catalog synchronization failed"):
        factory.create_vector_search_engine(
            index_path="/schemas/mitre.yaml",
            db=1,
            decode_responses=False,
            ssl=False,
        )

    spy_close.assert_called_once()


def test_create_vector_ingestion_engine_nominal(
    mocker, redis_driver_factory, mock_redis_vl_search_index: MagicMock
) -> None:
    """Nominal: instantiates IngestionCacheClient with RESP2 driver and initializes search index."""
    mocker.patch("src.persistence.engine.redis.redis_factory.redis_factory.RedisDriver", side_effect=redis_driver_factory)
    mock_redis_vl_search_index.exists.return_value = False
    factory = RedisPersistenceFactory()

    client = factory.create_vector_ingestion_engine(
        index_path="/schemas/mitre.yaml",
        target_vector_field="text_embedding",
        semantic_hashes_key="mitre:hashes",
        db=1,
        decode_responses=True,
        ssl=False,
    )

    assert isinstance(client, IngestionCacheClient)
    assert client._driver._vector_capability is True
    assert client._driver._client is not None
    mock_redis_vl_search_index.create.assert_called_once()


def test_create_vector_ingestion_engine_closes_driver_on_index_init_failure(
    mocker, redis_driver_factory, mock_redis_vl_search_index: MagicMock
) -> None:
    """Rollback: closes driver connection pool and re-raises if search index creation fails."""
    mocker.patch("src.persistence.engine.redis.redis_factory.redis_factory.RedisDriver", side_effect=redis_driver_factory)
    spy_close = mocker.spy(RedisDriver, "close")
    mock_redis_vl_search_index.exists.return_value = False
    mock_redis_vl_search_index.create.side_effect = RuntimeError("Index creation failed")
    factory = RedisPersistenceFactory()

    with pytest.raises(RuntimeError, match="Index creation failed"):
        factory.create_vector_ingestion_engine(
            index_path="/schemas/mitre.yaml",
            target_vector_field="text_embedding",
            semantic_hashes_key="mitre:hashes",
            db=1,
            decode_responses=True,
            ssl=False,
        )

    spy_close.assert_called_once()