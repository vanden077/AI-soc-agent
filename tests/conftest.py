from pathlib import Path

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from src.main import app

from src.schemas import Settings
from src.shared.cache import RedisClient

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
        INDEX_NAME="mitre_attack_v1"
    )

@pytest.fixture(scope="function")
def mock_settings(_session_settings) -> Settings:
    """Return an isolated copy of _session_settings for each tests"""
    return _session_settings.model_copy()


@pytest.fixture(scope="function")
def client(test_settings, monkeypatch):
    """Isolated Test Client for routes."""
    # catch Settings instance into lifespan
    monkeypatch.setattr("src.schemas.Settings", lambda *args, **kwargs: test_settings)

    with TestClient(app) as c:
        yield c


########## REDIS JSON ##########
@pytest.fixture(scope="function")
def redis(mocker):
    """
    Fixture simulating a fake Redis server usable through our custom redis_client
    FakeRedis is a pure-Python implementation of the Redis key-value store.
    https://fakeredis.readthedocs.io/en/latest/
    """
    cache_client = None
    redis_mock = mocker.patch(
        "src.shared.cache.driver.redis_driver.Redis",
        return_value=FakeRedis(),
    )

    try:
        cache_client = RedisClient(
            host="127.0.0.1",
            port=1,
            username="username",
            password="test",
            max_size_pool=CACHE_MAX_POOL_SIZE,
            retry_strategy=3,
        )
        cache_client.init_pool()
        assert redis_mock.called
    except Exception as err:  # noqa: BLE001
        print(f"Error Redis cache while creating connection pool: {err}")
    finally:
        yield cache_client


@pytest.fixture(scope="function")
def flush_cache(redis):
    """
    Cleanup cache between each test and release connections pool
    """
    if redis is not None:
        redis.flushdb()
        redis.close()
