from pathlib import Path
from unittest.mock import patch

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from langchain_huggingface import HuggingFaceEmbeddings

from src.embedding import EmbeddingManager
from src.common.cache import RedisClient, RedisVectorClient
from src.common.constants import Settings
from src.main import app

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
        REDIS_VECTOR_POOL_SIZE=5,
        REDIS_RETRY_STRATEGY=3,
        REDIS_SSL=False,
        INDEX_NAME="mitre_attack_v1",
        EMBEDDING_ENGINE="huggingface",
        EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
    )

@pytest.fixture(scope="function")
def mock_settings(_session_settings: Settings) -> Settings:
    """Return an isolated copy of _session_settings for each tests"""
    return _session_settings.model_copy()


########## EMBEDDING ENGINE ##########
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
    """Global fixture replacing Redis instance by FakeRedis"""
    return mocker.patch(
        "src.common.cache.driver.redis_driver.Redis",
        side_effect=FakeRedis
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
            max_size_pool=5,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            decode_responses=True,
            ssl=mock_settings.REDIS_SSL,
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
            max_size_pool=10,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            decode_responses=False,
            ssl=mock_settings.REDIS_SSL,
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

########## HTTP TEST CLIENT ##########
@pytest.fixture(scope="function")
def mock_client(
        mock_settings: Settings,
        json_cache: RedisClient,
        mock_embedding_engine: EmbeddingManager,
        vector_cache: RedisClient,
        monkeypatch):
    """Isolated Test Client for routes."""
    # inject fake env vars to stay iso-prod
    for key, value in mock_settings.model_dump(mode="json").items():
        if value is not None:
            monkeypatch.setenv(key, str(value))

    # replace RedisClient instance by fixture using FakeRedis
    with patch("src.common.cache.RedisClient", return_value=json_cache):
        with patch("src.common.cache.RedisVectorClient", return_value=vector_cache):
            # CRITICAL FIX: Patch the heavy LangChain constructor *BEFORE* entering the TestClient.
            # This ensures that when FastAPI triggers the real production 'lifespan' function,
            # it builds a lightweight "empty shell" instead of loading full PyTorch/Torch weights.
            with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None):
                with TestClient(app) as c:
                    # inject settings instance into FastApi context
                    c.app.state.settings = mock_settings
                    # inject redis instances into FastApi context
                    c.app.state.json_cache = json_cache
                    c.app.state.embedding_engine = mock_embedding_engine
                    c.app.state.vector_cache = vector_cache
                    yield c
