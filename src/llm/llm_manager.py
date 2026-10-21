from typing import Any

from src.llm.engine import OllamaEngine
from src.llm.interfaces.llm_provider import LlmProvider
from src.llm.interfaces.i_llm_engine import ILlmEngine


class LlmManager:
    """
    Factory pattern for LLM engines.
    """
    def __init__(self, base_url: str, llm_engine: str, llm_model: str, temperature: float = 0.0):
        self._engine: ILlmEngine[Any]
        self._base_url = base_url
        self._llm_engine = llm_engine
        self._llm_model = llm_model
        self._temperature = temperature
        self._check_llm_provider_availability()

    def _check_llm_provider_availability(self) -> None:
        """Checks whether the LLM engine provider is available, and store its instance into self._engine.
        :raises ValueError: if the LLM engine provider is not available
        :return: None
        """
        try:
            provider_enum = LlmProvider(self._llm_engine)
        except ValueError:
            raise ValueError(
                f"Engine '{self._llm_engine}' not supported. Available engines: {[p.value for p in LlmProvider]}")

        match provider_enum:
            case LlmProvider.OLLAMA:
                self._engine = OllamaEngine(
                    base_url=self._base_url,
                    model_name=self._llm_model,
                    temperature=self._temperature
                )
            # add any other available engine here
            case _:
                raise NotImplementedError(f"Engine '{provider_enum}' is listed but not yet implemented.")

    @property
    def engine(self) -> ILlmEngine[Any]:
        """Get the llm engine"""
        return self._engine