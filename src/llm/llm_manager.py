import importlib
from typing import Any, ClassVar

from src.llm.interfaces.i_llm_engine import ILlmEngine
from src.llm.providers.llm_provider import LlmProvider


class LlmManager:
    """
    Factory pattern for LLM engines using lazy dynamic resolution.
    """

    _ENGINE_REGISTRY: ClassVar[dict[LlmProvider, str]] = {
        LlmProvider.OLLAMA: "src.llm.engine.ollama.ollama_engine.OllamaEngine",
    }

    def __init__(
        self, base_url: str, llm_engine: str, llm_model: str, temperature: float = 0.0
    ) -> None:
        self._engine: ILlmEngine[Any]
        self._base_url = base_url
        self._llm_engine = llm_engine
        self._llm_model = llm_model
        self._temperature = temperature
        self._check_llm_provider_availability()

    def _check_llm_provider_availability(self) -> None:
        """Resolve the requested LLM provider dynamically and instantiate its engine."""
        try:
            provider_enum = LlmProvider(self._llm_engine)
        except ValueError:
            raise ValueError(
                f"Engine '{self._llm_engine}' not supported. Available engines: {[p.value for p in LlmProvider]}"
            )

        engine_path = self._ENGINE_REGISTRY.get(provider_enum)
        if engine_path is None:
            raise NotImplementedError(
                f"Engine '{provider_enum}' is listed but not yet implemented."
            )

        engine_cls = self._load_engine_class(engine_path)
        self._engine = engine_cls(
            base_url=self._base_url,
            model_name=self._llm_model,
            temperature=self._temperature,
        )

    @staticmethod
    def _load_engine_class(dotted_path: str) -> type[ILlmEngine[Any]]:
        """Dynamically import an engine class from its dotted module path."""
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    @property
    def engine(self) -> ILlmEngine[Any]:
        """Get the active LLM engine."""
        return self._engine
