from abc import ABC, abstractmethod
from typing import Any


class IEmbeddingEngine(ABC):
    """Common interface for all embedding engines."""
    @abstractmethod
    def _init_embedding(self) -> None:
        """Function to initialize the embedding,
        it is easier for testing it if the instantiation is outside of the __init__ method."""

    @abstractmethod
    def embed_query(self, text: str) -> Any:
        """Run vector query from str"""

    # Add any other common function related to any other embedding needed below

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
    def embedding(self) -> Any:
        """Get the engine instance"""