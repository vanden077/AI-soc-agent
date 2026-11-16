from abc import ABC, abstractmethod
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class IVectorSearchEngine(ABC):
    """
    Domain-agnostic contract for semantic vector similarity search.
    Decouples AI workflows from underlying vector database implementations
    (e.g., RedisVL, Qdrant, pgvector).
    """

    @abstractmethod
    def similarity_search(
        self,
        query_vector: list[float],
        response_model: Type[T],
        vector_field: Optional[str] = None,
        filter_expression: Optional[dict[str, str]] = None,
        limit: int = 5,
    ) -> list[T]:
        """Executes a semantic nearest-neighbor search and hydrates results into `response_model`."""

    @abstractmethod
    def health(self) -> bool:
        """Checks whether the underlying vector search engine connection is healthy."""

    @abstractmethod
    def close(self) -> None:
        """Gracefully releases underlying vector storage connections."""