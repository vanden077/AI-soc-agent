from collections.abc import Callable, Generator

import pytest
from src.persistence.engine.redis.client.queue.redis_queue_client import (
    RedisQueueClient,
)
from src.persistence.engine.redis.driver.redis_driver import RedisDriver


@pytest.fixture(scope="function")
def queue_client(
        redis_driver_factory: Callable[..., RedisDriver],
) -> Generator[RedisQueueClient]:
    """Provide an initialized RedisQueueClient backed by an isolated FakeRedis driver."""
    driver = redis_driver_factory(decode_responses=True, ssl=False, db=0)
    driver.init_pool()
    client = RedisQueueClient(
        driver=driver,
        pending_key="soc:test:pending",
        done_key="soc:test:done",
        max_done_history=2,
    )
    yield client
    client._driver.flush_db()
    client.close()
