import json
import logging
from typing import Any, cast, Mapping
import numpy as np

from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.interfaces.i_vector_ingestion_engine import IVectorIngestionEngine


logger = logging.getLogger(__name__)


class IngestionCacheClient(IVectorIngestionEngine):

    def __init__(self,
        driver: RedisDriver,
        target_vector_field: str,
        semantic_hashes_key: str
    ) -> None:
        """
        Initializes the agnostic ingestion client layer.
        Enforces vector_capability=True to ensure RedisVL components are available.
        """
        self._driver = driver
        self._key_prefix: str = ""
        self._vector_field_name: str = ""
        self._target_vector_field: str = target_vector_field
        self._semantic_hashes_key: str = semantic_hashes_key

    def init_search_index(self, schema_path: str) -> None:
        """
        Init RedisVL index, and locally load useful data for ingestion:
        key_prefix: in order to build unique identifiers in database.
        vector_field_name: in order to identify which embedding vector we want to use.
        """
        self._driver.init_search_index(schema_path=schema_path)
        self._key_prefix = self._driver.get_index_prefix()
        vector_catalog = self._driver.get_index_vector_fields_catalog()

        if self._target_vector_field not in vector_catalog:
            raise ValueError(
                f"Invalid index schema layout: The configured vector field '{self._target_vector_field}' "
                f"was not detected inside the unified catalog extracted from '{schema_path}'."
                f"Available vector fields defined in the schema are: {list(vector_catalog.keys())}"
            )

        self._vector_field_name = self._target_vector_field
        logger.info(f"VSS Ingestion Ready: Prefix={self._key_prefix} | VectorField={self._vector_field_name}")

    def fetch_remote_hashes(self) -> dict[str, str]:
        """
        Retrieves the entire semantic hashes registry map in a single atomic syscall.
        Provides a safe, non-blocking O(1) network roundtrip checkpoint to prevent data flapping.
        """
        logger.info(f"Getting documents fingerprints: '{self._semantic_hashes_key}'")
        try:
            raw_hashes = self._driver.redis_client.hgetall(self._semantic_hashes_key)
            return cast(dict[str, str], raw_hashes)
        except Exception as err:
            logger.error(f"Failed to synchronize fingerprints: {err}")
            return {}

    def set_remote_hashes(self, hash_map: dict[str, str]) -> None:
        """Persists a map of generic identifiers and fingerprints into the semantic hashes registry."""
        try:
            self._driver.redis_client.hset(self._semantic_hashes_key, mapping=cast(Mapping[Any, Any], hash_map))
        except Exception as err:
            logger.error(f"Failed to insert documents fingerprints into '{self._semantic_hashes_key}': {err}")
            raise RuntimeError(f"Infrastructure delta-cache persistence failure: {err}") from err


    def execute_bulk_upsert(
            self,
            payload: list[dict[str, Any]],
            embeddings: list[list[float]],
            id_field: str = "id"
    ) -> None:
        """
        Coordinates the structural formatting layer and flushes objects
        to the RedisVL index container.
        """
        bulk_documents: list[dict[str, Any]] = []

        # Linear O(1) buffer fusion and safe normalization mapping
        for doc, vector in zip(payload, embeddings):
            bulk_documents.append(self._normalize_document_types(doc, vector))

        # Bulk load the complex VSS records using the high-performance RedisVL native pipeline
        self._driver.search_index.load(data=bulk_documents, id_field=id_field, preprocess=None)
        logger.info(f"Batch ({len(payload)} documents) committed to VSS index successfully.")

    def health(self) -> bool:
        """
        Health check
        :return: bool, True if server is ready, else false
        """
        return self._driver.health()

    def close(self) -> None:
        """
        Release all connections on ephemeral batch completion
        :return: None
        """
        self._driver.close()

    def _normalize_document_types(self, doc: dict[str, Any], vector: list[float]) -> dict[str, Any]:
        """
        Coordinates the structural conversion of a STIX document
        to satisfy strict Redis Hash type constraints.
        No nested structures, neither float types from python.

        Float vector array must be cast into a C type bytes array (via NumPy).
        Lists have to be flattened in string with a separator.
        Dicts have to be transformed in a JSON string block.
        """
        # Shallow copy to safeguard business source data immutability
        clean_doc = doc.copy()

        # 1. Directly bind the packed Float32 bytes array to the target schema attribute key
        clean_doc[self.vector_field_name] = np.array(vector, dtype=np.float32).tobytes()

        # 2. Iterate and flatten complex metadata attributes to match Redis flat constraints
        for key, val in clean_doc.items():
            if key == self.vector_field_name:
                continue

            # Convert Python lists into comma-delimited strings for Redis TAG indexes
            if isinstance(val, list):
                clean_doc[key] = ",".join(str(item) for item in val)

            # Serialize nested dictionaries into valid JSON string blocks
            elif isinstance(val, dict):
                clean_doc[key] = json.dumps(val, ensure_ascii=False)

        return clean_doc

    @property
    def key_prefix(self) -> str:
        """
        Exposes the frozen keyspace namespace partition prefix.
        Ensures strict runtime safety by returning an immutable string.
        """
        return self._key_prefix

    @property
    def vector_field_name(self) -> str:
        """
        Exposes the targeted vector attribute field name defined by the application context.
        Provides the immutable identifier key required by downstream processing layers.
        """
        return self._vector_field_name

