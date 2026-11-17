from abc import ABC, abstractmethod


class IQueueEngine(ABC):
    """
    Domain-agnostic contract for FIFO background job queuing and completion tracking.
    Decouples asynchronous ingestion endpoints and workers from underlying queue brokers.
    """

    @abstractmethod
    def enqueue(self, job_id: str) -> int:
        """Push a job identifier onto the pending queue and return the updated pending count."""

    @abstractmethod
    def dequeue(self) -> str | None:
        """Pop and return the next oldest job identifier (FIFO), or None if pending queue is empty."""

    @abstractmethod
    def mark_done(self, job_id: str) -> int:
        """Record a completed job identifier in the done index and return the updated done count."""

    @abstractmethod
    def pending_size(self) -> int:
        """Return the current number of pending jobs waiting in the queue."""

    @abstractmethod
    def get_pending(self) -> list[str]:
        """Return all pending job identifiers in FIFO order."""

    @abstractmethod
    def get_done(self) -> list[str]:
        """Return all completed job identifiers (most recent first)."""

    @abstractmethod
    def health(self) -> bool:
        """Checks whether the underlying queue broker connection is healthy."""

    @abstractmethod
    def close(self) -> None:
        """Gracefully releases underlying queue broker connections."""
