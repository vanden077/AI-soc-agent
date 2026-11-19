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
            pending_key: str,
            done_key: str,
            max_done_history: int = 100,
    ) -> None:
        self._driver = driver
        self._pending_key = pending_key
        self._done_key = done_key
        self._max_done_history = max_done_history

    def enqueue(self, job_id: str) -> int:
        """Push a job key onto the pending queue and return the updated pending count."""
        try:
            return int(self._driver.redis_client.lpush(self._pending_key, job_id))
        except Exception as err:
            logger.error(f"Queue client error while enqueuing job '{job_id}': {err}")
            raise

    def dequeue(self) -> str | None:
        """Pop and return the next oldest job key (FIFO), or None if pending queue is empty."""
        try:
            job_id = self._driver.redis_client.rpop(self._pending_key)
            return str(job_id) if job_id is not None else None
        except Exception as err:
            logger.error(f"Queue client error while dequeuing from '{self._pending_key}': {err}")
            raise

    def mark_done(self, job_id: str) -> int:
        """Record a completed job key in the done index and return the updated done count."""
        try:
            count = int(self._driver.redis_client.lpush(self._done_key, job_id))
            self._driver.redis_client.ltrim(self._done_key, 0, self._max_done_history - 1)
            return min(count, self._max_done_history)
        except Exception as err:
            logger.error(f"Queue client error while marking job '{job_id}' as done: {err}")
            raise

    def pending_size(self) -> int:
        """Return the current number of non-expired pending jobs waiting in the queue."""
        return len(self.get_pending())

    def get_pending(self) -> list[str]:
        """Return all non-expired pending job keys in FIFO order."""
        try:
            items = self._driver.redis_client.lrange(self._pending_key, 0, -1)
            raw_keys = [str(item) for item in reversed(items)]
            return self._filter_alive_ids(queue_key=self._pending_key, job_keys=raw_keys)
        except Exception as err:
            logger.error(f"Queue client error while listing pending jobs: {err}")
            raise

    def get_done(self) -> list[str]:
        """Return all non-expired completed job keys (most recent first)."""
        try:
            items = self._driver.redis_client.lrange(self._done_key, 0, -1)
            raw_keys = [str(item) for item in items]
            return self._filter_alive_ids(queue_key=self._done_key, job_keys=raw_keys)
        except Exception as err:
            logger.error(f"Queue client error while listing done jobs: {err}")
            raise

    def _filter_alive_ids(self, queue_key: str, job_keys: list[str]) -> list[str]:
        """Keep only job keys that still exist in Redis, pruning expired keys."""
        if not job_keys:
            return []

        pipe = self._driver.redis_client.pipeline(transaction=False)
        for job_key in job_keys:
            pipe.exists(job_key)
        exists_flags = pipe.execute()

        alive_keys: list[str] = []
        expired_keys: list[str] = []
        for job_key, is_alive in zip(job_keys, exists_flags, strict=True):
            if is_alive:
                alive_keys.append(job_key)
            else:
                expired_keys.append(job_key)

        if expired_keys:
            self._prune_expired_ids(queue_key=queue_key, expired_keys=expired_keys)

        return alive_keys

    def _prune_expired_ids(self, queue_key: str, expired_keys: list[str]) -> None:
        """Remove expired job keys from the given Redis list in a single pipeline."""
        try:
            pipe = self._driver.redis_client.pipeline(transaction=False)
            for expired_key in expired_keys:
                pipe.lrem(queue_key, 0, expired_key)
            pipe.execute()
        except Exception as err:
            logger.warning(
                f"Queue client failed to prune {len(expired_keys)} expired job keys from '{queue_key}': {err}"
            )

    def health(self) -> bool:
        """Checks whether the underlying queue broker connection is healthy."""
        return self._driver.health()

    def close(self) -> None:
        """Gracefully releases underlying queue broker connections."""
        self._driver.close()
