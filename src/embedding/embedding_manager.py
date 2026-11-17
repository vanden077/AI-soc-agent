import importlib
from typing import Any, ClassVar

from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.embedding.providers.embedding_provider import EmbeddingProvider


class EmbeddingManager:
    """
    Factory pattern for embedding engines using lazy dynamic resolution.
    """

    _ENGINE_REGISTRY: ClassVar[dict[EmbeddingProvider, str]] = {
        EmbeddingProvider.HUGGINGFACE: "src.embedding.engine.huggingface.huggingface_engine.HuggingFaceEngine",
    }

    def __init__(self, provider: str, model_name: str) -> None:
        self._engine: IEmbeddingEngine[Any]
        self._provider = provider
        self._model_name = model_name
        self._check_embedding_provider_availability()

    def _check_embedding_provider_availability(self) -> None:
        """Resolve the requested embedding provider dynamically and instantiate its engine."""
        try:
            provider_enum = EmbeddingProvider(self._provider)
        except ValueError:
            raise ValueError(
                f"Engine '{self._provider}' not supported. Available engines: {[p.value for p in EmbeddingProvider]}"
            )

        engine_path = self._ENGINE_REGISTRY.get(provider_enum)
        if engine_path is None:
            raise NotImplementedError(
                f"Engine '{provider_enum}' is listed but not yet implemented."
            )

        engine_cls = self._load_engine_class(engine_path)
        self._engine = engine_cls(model_name=self._model_name)

    @staticmethod
    def _load_engine_class(dotted_path: str) -> type[IEmbeddingEngine[Any]]:
        """Dynamically import an engine class from its dotted module path."""
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    @property
    def engine(self) -> IEmbeddingEngine[Any]:
        """Get the active embedding engine."""
        return self._engine
