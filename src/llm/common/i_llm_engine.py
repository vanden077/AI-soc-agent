from abc import ABC, abstractmethod
from typing import Any

class ILlmEngine(ABC):
    """Common interface for all llm engines."""

    @abstractmethod
    def _init_llm(self) -> Any:
        """initialization method to allow clean mocking boundaries for structured output."""

    @staticmethod
    @abstractmethod
    def _format_message(state: Any) -> list[tuple[str, str]]:
        """Prepares and formats system and user messages for the LLM."""

    @abstractmethod
    def analyze_event(self, state: Any) -> Any:
        """Analyzes the current event and returns a valid pydantic model."""

    # Add any other common function related to any other llm needed below

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