from abc import ABC, abstractmethod
from typing import Any

from src.persistence.interfaces.i_json_storage_engine import IJsonStorageEngine
from src.persistence.interfaces.i_queue_engine import IQueueEngine
from src.persistence.interfaces.i_vector_ingestion_engine import IVectorIngestionEngine
from src.persistence.interfaces.i_vector_search_engine import IVectorSearchEngine


class IPersistenceFactory(ABC):
    """
    Abstract factory contract implemented by each persistence backend
    to encapsulate driver wiring and pool isolation without leaking backend-specific parameters.
    """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
    def create_queue_engine(
            self,
            pending_key: str,
            done_key: str,
            max_done_history: int = 100,
            **connection_kwargs: Any,
    ) -> IQueueEngine:
        """Instantiate and initialize an isolated FIFO job queue engine.

        Args:
            pending_key: Key or namespace storing pending job identifiers in FIFO order.
            done_key: Key or namespace storing completed job identifiers.
            max_done_history: Maximum number of completed job identifiers retained in history.
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
            IQueueEngine: Ready-to-use FIFO queue client bound to an isolated pool.
        """
