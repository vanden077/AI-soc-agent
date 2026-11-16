from abc import ABC, abstractmethod
from typing import Any


class IVectorIngestionEngine(ABC):
    """
    Domain-agnostic contract for batch vector ingestion and delta fingerprint tracking.
    Decouples data pipelines from underlying vector database implementations.
    """

    @abstractmethod
    def fetch_remote_hashes(self) -> dict[str, str]:
        """Retrieves the remote semantic hashes registry map for delta deduplication."""

    @abstractmethod
    def set_remote_hashes(self, hash_map: dict[str, str]) -> None:
        """Persists a map of document identifiers and semantic fingerprints."""

    @abstractmethod
    def execute_bulk_upsert(
        self,
        payload: list[dict[str, Any]],
        embeddings: list[list[float]],
        id_field: str = "id",
    ) -> None:
        """Formats and bulk-loads documents alongside their computed embeddings."""

    @abstractmethod
    def health(self) -> bool:
        """Checks whether the underlying ingestion storage connection is healthy."""

    @abstractmethod
    def close(self) -> None:
        """Gracefully releases underlying ephemeral ingestion connections."""