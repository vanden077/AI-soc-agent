from pathlib import Path
from unittest.mock import patch

import pytest
from fakeredis import FakeRedis, FakeServer
from langchain_huggingface import HuggingFaceEmbeddings

from src.embedding import EmbeddingManager
from src.common.cache import RedisClient, RedisVectorClient
from src.common.constants import Settings


CACHE_MAX_POOL_SIZE = 10

########## ENV VARS ##########
@pytest.fixture(scope="session")
def _session_settings() -> Settings:
    """Instanciate only once per test session"""
    return Settings(
        ENV="unit tests",
        MITRE_STIX_URL="https://fake_mitre_stix_url.com",
        MITRE_JSON_PATH=Path("fake_mitre_json_path"),
        REDIS_HOST="127.0.0.1",
        REDIS_PORT=6379,
        REDIS_USERNAME="default",
        REDIS_PASSWORD="",
        REDIS_JSON_POOL_SIZE=5,
        REDIS_VECTOR_POOL_SIZE=10,
        REDIS_RETRY_STRATEGY=3,
        REDIS_SSL=False,
        INDEX_NAME="mitre_attack_v1",
        REDIS_JSON_POOL_DB_ID=0,
        REDIS_VECTOR_POOL_DB_ID=1,
        EMBEDDING_ENGINE="huggingface",
        EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2",
        LLM_ENGINE="ollama",
        LLM_MODEL="llama3.1",
        LLM_URL="http://localhost:11434",
        LLM_TEMPERATURE=0.0
    )

@pytest.fixture(scope="function")
def mock_settings(_session_settings: Settings) -> Settings:
    """Return an isolated copy of _session_settings for each tests"""
    return _session_settings.model_copy()


# ########## EMBEDDING ENGINE ##########
@pytest.fixture(scope="function")
def mock_embedding_engine(mock_settings: Settings) -> EmbeddingManager:
    with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None):
        return EmbeddingManager(
            provider=mock_settings.EMBEDDING_ENGINE,
            model_name=mock_settings.EMBEDDING_MODEL_NAME
        )


########## REDIS ##########
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

########## REDIS JSON CLIENT ##########
@pytest.fixture(scope="function")
def json_cache(mock_settings: Settings):
    """
    Fixture simulating a fake Redis server usable through our custom redis_client
    FakeRedis is a pure-Python implementation of the Redis key-value store.
    https://fakeredis.readthedocs.io/en/latest/
    """
    cache_client = None

    try:
        cache_client = RedisClient(
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_JSON_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            decode_responses=True,
            ssl=mock_settings.REDIS_SSL,
            db=mock_settings.REDIS_JSON_POOL_DB_ID
        )
        cache_client.init_pool()
    except Exception as err:  # noqa: BLE001
        print(f"Error Redis cache while creating connection pool: {err}")
    finally:
        yield cache_client

########## REDIS VECTOR CLIENT ##########
@pytest.fixture(scope="function")
def vector_cache(mock_settings: Settings, mock_embedding_engine: EmbeddingManager):
    """
    Fixture simulating a fake Redis server usable through our custom redis_client
    FakeRedis is a pure-Python implementation of the Redis key-value store.
    https://fakeredis.readthedocs.io/en/latest/
    """
    cache_client = None

    try:
        cache_client = RedisVectorClient(
            embedding_model=mock_embedding_engine.engine,
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            decode_responses=False,
            ssl=mock_settings.REDIS_SSL,
            db=mock_settings.REDIS_VECTOR_POOL_DB_ID
        )
        cache_client.init_pool()
    except Exception as err:  # noqa: BLE001
        print(f"Error Redis cache while creating connection pool: {err}")
    finally:
        yield cache_client

@pytest.fixture(scope="function")
def flush_json_cache(json_cache: RedisClient):
    """
    Cleanup cache between each test and release connections pool
    """
    if json_cache is not None:
        json_cache.flushdb()
        json_cache.close()
