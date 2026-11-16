from typing import Callable, Generator

import pytest

from src.persistence.engine.redis.client.json.json_cache_client import JsonCacheClient
from src.persistence.engine.redis.driver.redis_driver import RedisDriver


@pytest.fixture(scope="function")
def json_cache(
    redis_driver_factory: Callable[..., RedisDriver],
) -> Generator[JsonCacheClient, None, None]:
    """Provide an initialized JsonCacheClient backed by an isolated FakeRedis driver."""
    driver = redis_driver_factory(decode_responses=True, ssl=False, db=0)
    driver.init_pool()
    yield JsonCacheClient(driver=driver)


@pytest.fixture(scope="function")
def flush_json_cache(json_cache: JsonCacheClient) -> None:
    """Cleanup persistence between each test and release connections pool."""
    json_cache._driver.flush_db()
    json_cache.close()