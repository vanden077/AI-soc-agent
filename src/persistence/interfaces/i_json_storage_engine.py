from abc import ABC, abstractmethod
from typing import Any, Mapping


class IJsonStorageEngine(ABC):
    """
    Domain-agnostic contract for JSON document persistence.
    Decouples application services and async queues from underlying storage engines.
    """

    @abstractmethod
    def get(self, key: str) -> str | int | float | bool | None | Mapping[str, Any] | list[Any]:
        """Retrieves a JSON document stored under `key`, or None if missing."""

    @abstractmethod
    def insert(self, key: str, data: dict[str, Any], ttl: int = 3600) -> bool:
        """Persists a JSON-serializable dictionary under `key` with an expiration TTL in seconds."""

    @abstractmethod
    def delete(self, key: str) -> int:
        """Deletes the entry identified by `key` and returns the number of removed keys."""

    @abstractmethod
    def health(self) -> bool:
        """Checks whether the underlying document storage connection is healthy."""

    @abstractmethod
    def close(self) -> None:
        """Gracefully releases underlying storage connections."""