from abc import ABC, abstractmethod

from pydantic import BaseModel


class IVectorSearchEngine(ABC):
    """
    Domain-agnostic contract for semantic vector similarity search.
    Decouples AI workflows from underlying vector database implementations
    (e.g., RedisVL, Qdrant, pgvector).
    """

    @abstractmethod
    def similarity_search[T: BaseModel](
            self,
            query_vector: list[float],
            response_model: type[T],
            vector_field: str | None = None,
            filter_expression: dict[str, str] | None = None,
            limit: int = 5,
    ) -> list[T]:
        """Executes a semantic nearest-neighbor search and hydrates results into `response_model`."""

    @abstractmethod
    def health(self) -> bool:
        """Checks whether the underlying vector search engine connection is healthy."""

    @abstractmethod
    def close(self) -> None:
        """Gracefully releases underlying vector storage connections."""
