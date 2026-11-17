import logging

from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.interfaces.i_queue_engine import IQueueEngine

logger = logging.getLogger(__name__)


class RedisQueueClient(IQueueEngine):
    """
    Redis client for FIFO background job queuing and completion tracking (RESP3).
    """

    def __init__(
            self,
            driver: RedisDriver,
            pending_key: str = "soc:queue:pending",
            done_key: str = "soc:queue:done",
            max_done_history: int = 100,
    ) -> None:
        self._driver = driver
        self._pending_key = pending_key
        self._done_key = done_key
        self._max_done_history = max_done_history

    def enqueue(self, job_id: str) -> int:
        """Push a job identifier onto the pending queue and return the updated pending count."""
        try:
            return int(self._driver.redis_client.lpush(self._pending_key, job_id))
        except Exception as err:
            logger.error(f"Queue client error while enqueuing job '{job_id}': {err}")
            raise

    def dequeue(self) -> str | None:
        """Pop and return the next oldest job identifier (FIFO), or None if pending queue is empty."""
        try:
            job_id = self._driver.redis_client.rpop(self._pending_key)
            return str(job_id) if job_id is not None else None
        except Exception as err:
            logger.error(f"Queue client error while dequeuing from '{self._pending_key}': {err}")
            raise

    def mark_done(self, job_id: str) -> int:
        """Record a completed job identifier in the done index and return the updated done count."""
        try:
            count = int(self._driver.redis_client.lpush(self._done_key, job_id))
            self._driver.redis_client.ltrim(self._done_key, 0, self._max_done_history - 1)
            return min(count, self._max_done_history)
        except Exception as err:
            logger.error(f"Queue client error while marking job '{job_id}' as done: {err}")
            raise

    def pending_size(self) -> int:
        """Return the current number of pending jobs waiting in the queue."""
        try:
            return int(self._driver.redis_client.llen(self._pending_key))
        except Exception as err:
            logger.error(f"Queue client error while reading pending queue size: {err}")
            raise

    def get_pending(self) -> list[str]:
        """Return all pending job identifiers in FIFO order."""
        try:
            items = self._driver.redis_client.lrange(self._pending_key, 0, -1)
            return [str(item) for item in reversed(items)]
        except Exception as err:
            logger.error(f"Queue client error while listing pending jobs: {err}")
            raise

    def get_done(self) -> list[str]:
        """Return all completed job identifiers (most recent first)."""
        try:
            items = self._driver.redis_client.lrange(self._done_key, 0, -1)
            return [str(item) for item in items]
        except Exception as err:
            logger.error(f"Queue client error while listing done jobs: {err}")
            raise

    def health(self) -> bool:
        """Checks whether the underlying queue broker connection is healthy."""
        return self._driver.health()

    def close(self) -> None:
        """Gracefully releases underlying queue broker connections."""
        self._driver.close()
