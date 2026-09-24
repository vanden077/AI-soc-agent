import pytest
from fakeredis import FakeRedis

from src.shared.cache import RedisClient

CACHE_MAX_POOL_SIZE = 10


########## REDIS ##########
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
