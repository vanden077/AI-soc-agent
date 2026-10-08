from abc import ABC, abstractmethod
from typing import Any, TypeVar, Type

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class ILlmEngine(ABC):
    """Common interface for all llm engines."""

    @abstractmethod
    def _init_llm(self) -> Any:
        """initialization method to allow clean mocking boundaries for structured output."""

    @abstractmethod
    def analyze_event(self, prompt: list[tuple[str, str]], response_schema: Type[T]) -> T:
        """
        Generate a structured response based on any arbitrary Pydantic schema.

        :param prompt: List of tuples representing (role, content), e.g., [("system", "..."), ("user", "...")]
        :param response_schema: The Pydantic class definition to enforce.
        :return: An instance of the provided response_schema class.
        """

    # @staticmethod
    # @abstractmethod
    # def _format_message(state: Any) -> list[tuple[str, str]]:
    #     """Prepares and formats system and user messages for the LLM."""
    #
    # @abstractmethod
    # def analyze_event(self, state: Any) -> Any:
    #     """Analyzes the current event and returns a valid pydantic model."""

    # Add any other interfaces function related to any other llm needed below

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Get the name of the LLM engine."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """URL of the current LLM"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name"""

    @property
    @abstractmethod
    def temperature(self) -> float:
        """Indication for the degree of freedom of the model,
        0 = precise/deterministic,
        more than 0 add randomness, creativity"""