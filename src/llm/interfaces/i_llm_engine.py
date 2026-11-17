from abc import ABC, abstractmethod

from pydantic import BaseModel


class ILlmEngine[TLLMEngine](ABC):
    """Common interface for all llm engines."""

    @abstractmethod
    def __init__(
            self, base_url: str, model_name: str, temperature: float = 0.0
    ) -> None:
        """Initialize the LLM engine with standard connection and inference parameters."""

    @abstractmethod
    def _init_llm(self) -> TLLMEngine:
        """initialization method to allow clean mocking boundaries for structured output."""

    @abstractmethod
    def analyze_event[T: BaseModel](
            self, prompt: list[tuple[str, str]], response_schema: type[T]
    ) -> T:
        """
        Generate a structured response based on any arbitrary Pydantic schema.

        :param prompt: List of tuples representing (role, content), e.g., [("system", "..."), ("user", "...")]
        :param response_schema: The Pydantic class definition to enforce.
        :return: An instance of the provided response_schema class.
        """

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
