from abc import ABC, abstractmethod
from typing import Any


class IEmbeddingEngine[EmbEngine](ABC):
    """Common interface for all embedding engines."""

    @abstractmethod
    def __init__(self, model_name: str) -> None:
        """Initialize the embedding engine class."""

    @abstractmethod
    def _init_embedding(self) -> EmbEngine:
        """Function to initialize the embedding,
        it is easier for testing it if the instantiation is outside of the __init__ method."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Run vector query from str"""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]] | Any:
        """
        Run high-performance bulk vector generation from a list of strings.
        Leverages underlying engine optimizations (AVX/SIMD/Batch size).
        """

    # Add any other interfaces function related to any other embedding needed below

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Get the engine name"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name"""

    @property
    @abstractmethod
    def embedding(self) -> EmbEngine:
        """Get the engine instance"""
