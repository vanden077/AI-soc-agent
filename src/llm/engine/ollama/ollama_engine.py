import logging
from typing import Type, cast

from langchain_ollama import ChatOllama
from pydantic import ValidationError

from src.llm.interfaces.i_llm_engine import ILlmEngine, T

logger = logging.getLogger()

class OllamaEngine(ILlmEngine[ChatOllama]):
    """LLM wrapper engine"""

    def __init__(self, base_url: str, model_name: str, temperature: float = 0.0):
        self._engine_name = "Ollama"
        self._base_url = base_url
        self._model_name = model_name
        self._temperature = temperature
        self._llm = self._init_llm()

    def _init_llm(self) -> ChatOllama:
        """initialization method to allow clean mocking boundaries for structured output."""
        return ChatOllama(
            base_url=self._base_url,
            model=self._model_name,
            temperature=self._temperature,
            num_ctx=2048,
            num_predict=110,
            keep_alive="10m"
        )

    def analyze_event(self, prompt: list[tuple[str, str]], response_schema: Type[T]) -> T:
        """
        Analyze a contextual event and return a structured response (pydantic schema).

         Raises:
             ValidationError: If the LLM output violates Pydantic v2 constraints.
             Exception: For connection or Ollama API failures.
        """
        structured_llm = self._llm.with_structured_output(response_schema)

        try:
            return cast(T, structured_llm.invoke(prompt))
        except ValidationError as ve:
            logger.error(f"Pydantic validation failed on LLM output: {ve.json()}")
            raise
        except Exception as e:
            logger.error(f"Ollama API call failed: {str(e)}")
            raise

    @property
    def engine_name(self) -> str:
        return self._engine_name

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature
