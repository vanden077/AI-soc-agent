import pytest

from src.common.cache import JsonCacheClient


@pytest.fixture(scope="function")
def json_cache(mock_redis_driver):
    """
    Fixture using FakeRedis driver.
    FakeRedis is a pure-Python implementation of the Redis key-value store.
    https://fakeredis.readthedocs.io/en/latest/
    """
    json_cache = JsonCacheClient(
        host="test",
        port=1,
        username="username",
        password="test",
        max_size_pool=1,
        retry_strategy=1,
        decode_responses=True,
        ssl=False,
        db=0
    )

    try:
        json_cache.init_pool()
    except Exception as err:  # noqa: BLE001
        print(f"Error Redis while creating JSON connection pool: {err}")
    finally:
        yield json_cache

@pytest.fixture(scope="function")
def flush_json_cache(json_cache: JsonCacheClient):
    """
    Cleanup cache between each test and release connections pool
    """
    if json_cache is not None:
        json_cache.flush_db()
        json_cache.close()