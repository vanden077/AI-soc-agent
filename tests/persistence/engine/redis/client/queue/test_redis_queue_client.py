import logging
from collections.abc import Callable
from unittest.mock import patch

import pytest

from src.persistence.engine.redis.client.queue.redis_queue_client import (
    RedisQueueClient,
)
from src.persistence.engine.redis.driver.redis_driver import RedisDriver


def _seed_alive_keys(
        redis_driver_factory: Callable[..., RedisDriver], *keys: str
) -> None:
    """Persist dummy keys in shared FakeServer so _filter_alive_ids treats them as non-expired."""
    helper_driver = redis_driver_factory(decode_responses=True, ssl=False, db=0)
    helper_driver.init_pool()
    try:
        for key in keys:
            helper_driver.redis_client.set(key, "1")
    finally:
        helper_driver.close()


def test_queue_client_enqueue(queue_client: RedisQueueClient) -> None:
    """Push jobs onto pending queue and return updated queue size."""
    assert queue_client.enqueue("job-1") == 1
    assert queue_client.enqueue("job-2") == 2


def test_queue_client_enqueue_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when lpush fails on enqueue."""
    mocker.patch(
        "redis.commands.core.ListCommands.lpush",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.enqueue("job-1")

    assert (
            "Queue client error while enqueuing job 'job-1': Mocked exception"
            in caplog.messages
    )


def test_queue_client_dequeue_fifo(queue_client: RedisQueueClient) -> None:
    """Pop oldest job identifier first in strict FIFO order."""
    queue_client.enqueue("job-1")
    queue_client.enqueue("job-2")

    assert queue_client.dequeue() == "job-1"
    assert queue_client.dequeue() == "job-2"


def test_queue_client_dequeue_empty(queue_client: RedisQueueClient) -> None:
    """Return None when pending queue is empty."""
    assert queue_client.dequeue() is None


def test_queue_client_dequeue_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when rpop fails on dequeue."""
    mocker.patch(
        "redis.commands.core.ListCommands.rpop",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.dequeue()

    assert (
            "Queue client error while dequeuing from 'soc:test:pending': Mocked exception"
            in caplog.messages
    )


def test_queue_client_mark_done_and_trim(
        queue_client: RedisQueueClient,
        redis_driver_factory: Callable[..., RedisDriver],
) -> None:
    """Record completed jobs newest-first and cap history to max_done_history."""
    _seed_alive_keys(redis_driver_factory, "job-1", "job-2", "job-3")
    assert queue_client.mark_done("job-1") == 1
    assert queue_client.mark_done("job-2") == 2
    assert queue_client.mark_done("job-3") == 2

    assert queue_client.get_done() == ["job-3", "job-2"]


def test_queue_client_mark_done_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when lpush fails on mark_done."""
    mocker.patch(
        "redis.commands.core.ListCommands.lpush",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.mark_done("job-1")

    assert (
            "Queue client error while marking job 'job-1' as done: Mocked exception"
            in caplog.messages
    )


def test_queue_client_pending_size(
        queue_client: RedisQueueClient,
        redis_driver_factory: Callable[..., RedisDriver],
) -> None:
    """Return current number of non-expired jobs waiting in the pending queue."""
    assert queue_client.pending_size() == 0
    _seed_alive_keys(redis_driver_factory, "job-1", "job-2")
    queue_client.enqueue("job-1")
    queue_client.enqueue("job-2")
    assert queue_client.pending_size() == 2


def test_queue_client_pending_size_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when lrange fails on pending_size."""
    mocker.patch(
        "redis.commands.core.ListCommands.lrange",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.pending_size()

    assert (
            "Queue client error while listing pending jobs: Mocked exception"
            in caplog.messages
    )


def test_queue_client_get_pending(
        queue_client: RedisQueueClient,
        redis_driver_factory: Callable[..., RedisDriver],
) -> None:
    """Return all non-expired pending job identifiers in FIFO order without mutating the queue."""
    assert queue_client.get_pending() == []
    _seed_alive_keys(redis_driver_factory, "job-1", "job-2")
    queue_client.enqueue("job-1")
    queue_client.enqueue("job-2")

    assert queue_client.get_pending() == ["job-1", "job-2"]
    assert queue_client.pending_size() == 2


def test_queue_client_get_pending_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when lrange fails on get_pending."""
    mocker.patch(
        "redis.commands.core.ListCommands.lrange",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.get_pending()

    assert (
            "Queue client error while listing pending jobs: Mocked exception"
            in caplog.messages
    )


def test_queue_client_get_done_exception(
        mocker, queue_client: RedisQueueClient, caplog
) -> None:
    """Log error and re-raise when lrange fails on get_done."""
    mocker.patch(
        "redis.commands.core.ListCommands.lrange",
        side_effect=Exception("Mocked exception"),
    )

    with pytest.raises(Exception, match="Mocked exception"):
        queue_client.get_done()

    assert (
            "Queue client error while listing done jobs: Mocked exception"
            in caplog.messages
    )


def test_queue_client_prunes_expired_keys_on_read(
        queue_client: RedisQueueClient,
        redis_driver_factory: Callable[..., RedisDriver],
) -> None:
    """Filter out expired keys and remove them from the underlying Redis list."""
    _seed_alive_keys(redis_driver_factory, "job-alive")
    queue_client.mark_done("job-expired")
    queue_client.mark_done("job-alive")

    assert queue_client.get_done() == ["job-alive"]
    assert queue_client.get_done() == ["job-alive"]


def test_queue_client_prune_expired_ids_logs_warning_on_failure(
        mocker,
        queue_client: RedisQueueClient,
        redis_driver_factory: Callable[..., RedisDriver],
        caplog,
) -> None:
    """Log a warning without failing reads when pruning expired keys raises an error."""
    _seed_alive_keys(redis_driver_factory, "job-alive")
    queue_client.mark_done("job-expired")
    queue_client.mark_done("job-alive")

    mocker.patch(
        "redis.commands.core.ListCommands.lrem",
        side_effect=RuntimeError("LREM boom"),
    )

    with caplog.at_level(logging.WARNING):
        assert queue_client.get_done() == ["job-alive"]

    assert (
            "Queue client failed to prune 1 expired job keys from 'soc:test:done': LREM boom"
            in caplog.messages
    )


def test_queue_client_health_delegates_to_driver(
        queue_client: RedisQueueClient,
) -> None:
    """Verify health() delegates directly to the underlying driver."""
    with patch.object(RedisDriver, "health", return_value=True) as mock_health:
        assert queue_client.health() is True
        mock_health.assert_called_once()


def test_queue_client_close_delegates_to_driver(
        queue_client: RedisQueueClient,
) -> None:
    """Verify close() delegates connection pool shutdown directly to the underlying driver."""
    with patch.object(RedisDriver, "close") as mock_close:
        queue_client.close()
        mock_close.assert_called_once()
