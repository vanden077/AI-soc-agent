import logging

from typing import Any, TypeVar, Sequence, Type, Optional

from pydantic import BaseModel
from redisvl.query import VectorQuery
from redisvl.query.filter import FilterExpression, Tag

from src.persistence.interfaces.i_vector_search_engine import IVectorSearchEngine
from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.engine.redis.driver.vector_fields_specs import VectorFieldSpecs
from src.persistence.engine.redis.client.vector.exceptions import VectorDimensionMismatchError
from src.persistence.engine.redis.geometric_guards import is_distance_valid, clamp_distance_result

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class VectorCacheClient(IVectorSearchEngine):
    """Agnostic vector search engine client.

    Consumes a direct single-source-of-truth O(1) schema map supplied natively by the parent 
    driver, achieving absolute zero-overhead metadata management during lifespan hooks.
    """

    def __init__(
            self,
            driver: RedisDriver,
            index_path: str
    ) -> None:
        self._driver = driver
        self._index_path = index_path
        # will contain all vectors available
        self._catalog: dict[str, VectorFieldSpecs] = {}
        # will contain all metadata defined in Redis index schema
        self._metadata_fields: set[str]

    def sync_lifespan_catalog(self) -> None:
        """Hooks into the parent workflow and directly stores the native O(1) specs map."""
        self._driver.init_search_index(self._index_path)
        self._catalog = self._driver.get_index_vector_fields_catalog()
        self._metadata_fields = self._driver.get_index_metadata_fields()

    def similarity_search(
            self,
            query_vector: list[float],
            response_model: Type[T],
            vector_field: Optional[str] = None,
            filter_expression: Optional[dict[str, str]] = None,
            limit: int = 5
    ) -> list[T]:
        """Performs a linear, hybrid semantic similarity search starting from raw text.

        This method acts as the single runtime entry point for semantic querying. It orchestrates
        strict O(1) geometric dimension guards to prevent lower-level Redis cluster crashes, and parses the
        resulting database entries into strong Pydantic domain models using an EAFP architecture.

        Args:
            query_vector list[float]: Text vectorized by any embedding engine. Cannot be empty.
            response_model (Type[T]): The expected target Pydantic schema used as response.
            vector_field (Optional[str], optional): The exact semantic tensor column name to execute
                the KNN search space against (e.g., "text_embedding", "code_embedding"). If None,
                automatically falls back to the unique available vector field discovered in the catalog.
                Defaults to None.
            filter_expression (Optional[dict[str, str], optional): A dict where key is the tag field you want to filter
                and the value is the filtering expression: {"platform": "windows"} Defaults to None.
            limit (int, optional): The maximum number of nearest neighbor records (Top-K) to return,
                sorted by relevance descending. Defaults to 5.

        Raises:
            ValueError: If the explicitly provided vector_field does not match the active cached index specifications schema catalog.
            VectorDimensionMismatchError: If the computed text vector array layout violates the rigid
                dimensional geometric_guards registered inside the Redis index schema catalog.
            RuntimeError: If a lower-level Redis protocol error occurs or the custom query alias is missing.

        Returns:
            list[T]: response as a list of Pydantic schema
        """
        # 1. Payload validation guard
        if not query_vector:
            return []

        # 2. Structural Field Resolution & Verification
        vector_name = self._validate_and_resolve_vector_field(vector_field=vector_field)
        target_specs = self.catalog[vector_name]
        fields_to_return = self._resolve_return_fields(response_model=response_model)

        # 3. Geometric Guard: Strict dimension alignment verification
        if len(query_vector) != target_specs.dimension:
            raise VectorDimensionMismatchError(
                f"Expected {target_specs.dimension} dimensions, got {len(query_vector)}"
            )

        # 4. Build standard RedisVL query object.
        # RedisVL automatically forces the target key to 'vector_distance' under the hood.
        query = VectorQuery(
            vector=query_vector,
            vector_field_name=vector_name,
            return_fields=fields_to_return,
            num_results=limit,
            filter_expression=self._build_tag_filter(metadata_tags=filter_expression)
        )
        results = self._driver.search_index.query(query)
        logger.info(f"[VECTOR CACHE RAW] type={type(results)} | payload={results}")

        # 5. Parse and clean results by binding the resolved field configuration
        return self._parse_and_clean_results(results=results, response_model=response_model, vector_name=vector_name)

    def _validate_and_resolve_vector_field(self, vector_field: Optional[str]) -> str:
        """Enforces runtime validation rules on the requested vector field.

        Ensures full geometric safety by rejecting ambiguities and missing fields
        before engaging network I/O operations (Fail-Fast).
        """
        # Rule 1: No vector_field supplied
        if vector_field is None:
            if len(self.catalog) == 1:
                return next(iter(self.catalog.keys()))

            raise ValueError(
                "Ambiguity in vector search: Multiple vector fields are configured in the index catalog, "
                "but none was specified. You must explicitly pass a 'vector_field' parameter to avoid "
                f"receiving aberrant semantic results. Available vector(s):  {self.available_vector_fields}"
            )

        # Rule 2: A vector_field was supplied but does not exist in the catalog
        if vector_field not in self.available_vector_fields:
            raise ValueError(
                f"Configuration Error: The requested vector field '{vector_field}' does not exist "
                f"in the cached Redis index schema catalog. Available fields are: {list(self.available_vector_fields)}"
            )

        return vector_field

    def _resolve_return_fields(self, response_model: Type[BaseModel]) -> list[str]:
        """Resolves the exact subset of metadata fields to fetch from Redis based on the target schema.

        Prevents fetching unrequested fields or heavy vector tensors over the network,
        and fails fast if the target Pydantic schema has zero overlap with the index metadata.
        """
        fields_to_return = [
            field_name for field_name in response_model.model_fields
            if field_name in self._metadata_fields
        ]

        if not fields_to_return:
            raise ValueError(
                f"Schema Mismatch Error: None of the fields declared in '{response_model.__name__}' "
                f"match the available index metadata fields: {sorted(self._metadata_fields)}"
            )

        return fields_to_return

    def _parse_and_clean_results(self, results: Sequence[dict[str, Any]], response_model: Type[T], vector_name: str) -> list[T]:
        """Filters tensor data, strips database technicalities, and computes a universal normalized similarity.

        Strict EAFP implementation. Any schema mismatch or database corruption triggers an immediate failure.
        """
        parsed_models = []
        # Retrieve specifications tied strictly to the queried vector field (Supports multi-vector contexts)
        specs = self.catalog[vector_name]

        for doc in results:
            doc_id = str(doc["id"])
            raw_distance = float(doc["vector_distance"])

            # Geometric Guard: trap IEEE 754 NaN or Inf values
            if not is_distance_valid(raw_distance=raw_distance, doc_id=doc_id):
                continue

            # Geometric Guard: clamp distance into [0.0, 1.0] similarity score
            normalized_similarity = clamp_distance_result(
                raw_distance=raw_distance,
                doc_id=doc_id,
                metric=specs.metric,
            )
            if normalized_similarity is None:
                continue

            payload = {**doc, "normalized_similarity": normalized_similarity}
            parsed_models.append(response_model.model_validate(payload))

        return parsed_models

    def health(self) -> bool:
        """
        Health check
        :return: bool, True if server is ready, else false
        """
        return self._driver.health()

    def close(self) -> None:
        """
        Release all connections on app shutdown event
        :return: None
        """
        self._driver.close()

    @staticmethod
    def _build_tag_filter(metadata_tags: Optional[dict[str, str]]) -> Optional[FilterExpression]:
        """
        Translates an agnostic key-value dictionary into a RedisVL FilterExpression.
        Keeps RedisVL filtering mechanics strictly isolated within the infrastructure layer.
        """
        if not metadata_tags:
            return None

        # !! CODE SMELL !!
        # RedisVL relies on Python's equality operator overloading (`Tag(k) == v`) to build
        # FilterExpression AST nodes instead of returning a boolean. This non-standard DSL
        # confuses static type checkers and is a prime candidate for breaking API changes
        # in future RedisVL releases. Isolated here to protect the domain layer.
        combined_filter: Optional[FilterExpression] = None
        for field, value in metadata_tags.items():
            clause: FilterExpression = Tag(field) == value  # type: ignore[assignment]
            combined_filter = clause if combined_filter is None else (combined_filter & clause)

        return combined_filter

    @property
    def catalog(self) -> dict[str, VectorFieldSpecs]:
        """
        Expose the vector fields specifications catalog.
        Provides downstream components with read-only access to geometric specs.
        """
        return self._catalog

    @property
    def metadata_fields(self) -> set[str]:
        """
        Expose the metadata fields catalog (e.g., 'text', 'tag', 'numeric')
        """
        return self._metadata_fields

    @property
    def available_vector_fields(self) -> set[str]:
        """Returns the exact list of string keys available to use in 'vector_field'."""
        return set(self._catalog.keys())
