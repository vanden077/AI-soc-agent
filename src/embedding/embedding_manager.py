from embedding.engine.huggingface.huggingface_engine import HuggingFaceEngine
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.embedding.interfaces.embedding_provider import EmbeddingProvider

class EmbeddingManager:
    """
    Factory pattern for embedding engines.
    """
    def __init__(self, provider: str, model_name: str):
        self._engine: IEmbeddingEngine
        self._provider = provider
        self._model_name = model_name
        self._check_embedding_provider_availability()

    def _check_embedding_provider_availability(self) -> None:
        """Checks whether the embedding provider is available, and store its instance into self._engine.
        :raises ValueError: if the embedding provider is not available
        :return: None
        """
        try:
            provider_enum = EmbeddingProvider(self._provider)
        except ValueError:
            raise ValueError(
                f"Engine '{self._provider}' not supported. Available engines: {[p.value for p in EmbeddingProvider]}")

        match provider_enum:
            case EmbeddingProvider.HUGGINGFACE:
                self._engine = HuggingFaceEngine(model_name=self._model_name)
            # add any other available engine here
            case _:
                raise NotImplementedError(f"Engine '{provider_enum}' is listed but not yet implemented.")

    @property
    def engine(self) -> IEmbeddingEngine:
        """Get the embedding engine"""
        return self._engine
