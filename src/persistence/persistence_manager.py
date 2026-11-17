import importlib
from collections.abc import Callable
from typing import Any, ClassVar

from src.persistence.interfaces.i_json_storage_engine import IJsonStorageEngine
from src.persistence.interfaces.i_persistence_factory import IPersistenceFactory
from src.persistence.interfaces.i_vector_ingestion_engine import IVectorIngestionEngine
from src.persistence.interfaces.i_vector_search_engine import IVectorSearchEngine
from src.persistence.providers.persistence_provider import PersistenceProvider


class PersistenceManager:
    """
    Factory distributor for persistence backends.
    Resolves the configured provider and delegates isolated engine instantiation to its factory.
    """

    _FACTORY_REGISTRY: ClassVar[dict[PersistenceProvider, str]] = {
        PersistenceProvider.REDIS: (
            "src.persistence.engine.redis.redis_factory.redis_factory.RedisPersistenceFactory"
        ),
    }

    def __init__(self, provider: str) -> None:
        self._factory: IPersistenceFactory
        self._provider = provider
        self._check_persistence_provider_availability()

    def _check_persistence_provider_availability(self) -> None:
        """Validate whether the persistence provider is available and instantiate its factory."""
        try:
            provider_enum = PersistenceProvider(self._provider)
        except ValueError:
            raise ValueError(
                f"Persistence provider '{self._provider}' not supported. "
                f"Available providers: {[p.value for p in PersistenceProvider]}"
            )

        factory_path = self._FACTORY_REGISTRY.get(provider_enum)
        if not factory_path:
            raise NotImplementedError(
                f"Persistence provider '{provider_enum}' is listed but not yet implemented."
            )

        factory_cls = self._load_engine_class(factory_path)
        self._factory = factory_cls()

    @staticmethod
    def _load_engine_class(dotted_path: str) -> Callable[[], IPersistenceFactory]:
        """Dynamically import a factory class from its dotted module path."""
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def create_json_engine(self, **connection_kwargs: Any) -> IJsonStorageEngine:
        """Instantiate and initialize an isolated JSON document storage engine.

        Args:
            **connection_kwargs: Backend connection and connection-pool parameters:
                - host (str | None): Target server hostname or IP. Defaults to "localhost".
                - port (int | None): Target server TCP port. Defaults to 6379.
                - ssl (bool): Enable TLS/SSL encryption. Defaults to True.
                - username (str | None): Authentication username. Defaults to None.
                - password (str | None): Authentication password. Defaults to None.
                - max_size_pool (int): Maximum concurrent connections in the isolated pool. Defaults to 50.
                - retry_strategy (int): Maximum retry attempts on transient network failure. Defaults to 3.
                - decode_responses (bool): Automatically decode raw bytes to UTF-8 strings. Defaults to True.
                - db (int): Logical database index for namespace isolation. Defaults to 0.

        Returns:
            IJsonStorageEngine: Ready-to-use JSON storage client bound to an isolated pool.
        """
        return self._factory.create_json_engine(**connection_kwargs)

    def create_vector_search_engine(
        self, index_path: str, **connection_kwargs: Any
    ) -> IVectorSearchEngine:
        """Instantiate and initialize a read-only semantic vector search engine.

        Args:
            index_path: Local filesystem path to the vector index schema definition (YAML).
            **connection_kwargs: Backend connection and connection-pool parameters:
                - host (str | None): Target server hostname or IP. Defaults to "localhost".
                - port (int | None): Target server TCP port. Defaults to 6379.
                - ssl (bool): Enable TLS/SSL encryption. Defaults to True.
                - username (str | None): Authentication username. Defaults to None.
                - password (str | None): Authentication password. Defaults to None.
                - max_size_pool (int): Maximum concurrent connections in the isolated pool. Defaults to 50.
                - retry_strategy (int): Maximum retry attempts on transient network failure. Defaults to 3.
                - decode_responses (bool): Automatically decode raw bytes to UTF-8 strings.
                  Recommended False for binary vector payloads.
                - db (int): Logical database index for namespace isolation. Defaults to 0.

        Returns:
            IVectorSearchEngine: Ready-to-use semantic search client with synchronized index metadata and isolated pool.
        """
        return self._factory.create_vector_search_engine(
            index_path=index_path, **connection_kwargs
        )

    def create_vector_ingestion_engine(
        self,
        index_path: str,
        target_vector_field: str,
        semantic_hashes_key: str,
        **connection_kwargs: Any,
    ) -> IVectorIngestionEngine:
        """Instantiate and initialize an ephemeral batch vector ingestion engine.

        Caller is responsible for releasing resources via `.close()` once ingestion completes.

        Args:
            index_path: Local filesystem path to the vector index schema definition (YAML).
            target_vector_field: Target vector attribute name declared in the index schema.
            semantic_hashes_key: Key or namespace storing document fingerprints for delta updates.
            **connection_kwargs: Backend connection and connection-pool parameters:
                - host (str | None): Target server hostname or IP. Defaults to "localhost".
                - port (int | None): Target server TCP port. Defaults to 6379.
                - ssl (bool): Enable TLS/SSL encryption. Defaults to True.
                - username (str | None): Authentication username. Defaults to None.
                - password (str | None): Authentication password. Defaults to None.
                - max_size_pool (int): Maximum concurrent connections in the isolated pool. Defaults to 50.
                - retry_strategy (int): Maximum retry attempts on transient network failure. Defaults to 3.
                - decode_responses (bool): Automatically decode raw bytes to UTF-8 strings. Defaults to True.
                - db (int): Logical database index for namespace isolation. Defaults to 0.

        Returns:
            IVectorIngestionEngine: Ready-to-use batch ingestion client bound to an ephemeral pool.
        """
        return self._factory.create_vector_ingestion_engine(
            index_path=index_path,
            target_vector_field=target_vector_field,
            semantic_hashes_key=semantic_hashes_key,
            **connection_kwargs,
        )
