import logging
import math
from typing import Any, TypeVar, Sequence, Type, Optional

from pydantic import BaseModel
from redisvl.query import VectorQuery

from src.common.cache.client.vector.exceptions import EmptyVectorError, VectorDimensionMismatchError
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.common.cache.driver.vector_fields_specs import VectorFieldSpecs
from src.common.cache.driver.redis_driver import RedisDriver

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class VectorCacheClient(RedisDriver):
    """High-performance, agnostic vector cache client built for FastAPI Lifespan context.

    Consumes a direct single-source-of-truth O(1) schema map supplied natively by the parent 
    driver, achieving absolute zero-overhead metadata management during lifespan hooks.
    """

    def __init__(
            self,
            *args: Any,
            index_name: str,
            embedding_engine: IEmbeddingEngine[Any],
            **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._index_name = index_name
        self._embedding_engine = embedding_engine
        # will contain all vectors available when lifespan will be synced
        self._catalog: dict[str, VectorFieldSpecs] = {}

    def sync_lifespan_catalog(self) -> None:
        """Hooks into the parent workflow and directly stores the native O(1) specs map."""
        super().set_search_index(self._index_name)

        try:
            self._catalog = self.get_index_vector_fields_catalog()

            logger.info(
                f"Successfully unified vector client with index '{self._index_name}' - "
                f"O(1) catalog mounted with {len(self._catalog)} verified tensor paths."
            )
        except (ValueError, RuntimeError) as err:
            logger.critical(f"Critical configuration failure during vector lifespan sync: {err}")
            raise err

    def similarity_search(
            self,
            query_text: str,
            response_model: Type[T],
            vector_field: Optional[str] = None,
            filter_expression: Optional[Any] = None,
            limit: int = 5
    ) -> list[T]:
        """Performs a linear, hybrid semantic similarity search starting from raw text.

        This method acts as the single runtime entry point for semantic querying. It orchestrates
        on-the-fly text vectorization via the injected embedding engine, enforces strict O(1)
        geometric dimension guards to prevent lower-level Redis cluster crashes, and parses the
        resulting database entries into strong Pydantic domain models using an EAFP architecture.

        Args:
            query_text (str): The raw input string payload to materialize and search for. Cannot be blank.
            response_model (Type[T]): The expected target Pydantic schema used as response.
            vector_field (Optional[str], optional): The exact semantic tensor column name to execute
                the KNN search space against (e.g., "text_embedding", "code_embedding"). If None,
                automatically falls back to the unique available vector field discovered in the catalog.
                Defaults to None.
            filter_expression (Optional[Any], optional): A native RedisVL `FilterExpression` object used
                to apply metadata pre-filtering (e.g., platform, matrix or tags) in O(1) before running
                the vector search. Defaults to None.
            limit (int, optional): The maximum number of nearest neighbor records (Top-K) to return,
                sorted by relevance descending. Defaults to 5.

        Raises:
            ValueError: If the query_text payload is empty/blank, or if the explicitly provided
                vector_field does not match the active cached index specifications schema catalog.
            EmptyVectorError: If the abstract embedding engine returns an empty float array.
            VectorDimensionMismatchError: If the computed text vector array layout violates the rigid
                dimensional geometry registered inside the Redis index schema catalog.
            RuntimeError: If a lower-level Redis protocol error occurs or the custom query alias is missing.

        Returns:
            list[T]: response as a list of Pydantic schema
        """
        # 1. Payload validation guard
        if not query_text or not query_text.strip():
            # you want nothing ? ok i can give it to you without crashing.
            return []

        # 2. On-the-fly text vectorization via the abstract engine
        query_vector = self._embedding_engine.embed_query(query_text)

        if not query_vector:
            raise EmptyVectorError("Vector cannot be empty")

        # 3. Structural Field Resolution & Verification (Executes Rules 1, 2, and 3)
        resolved_field = self._validate_and_resolve_vector_field(vector_field)
        target_specs = self.catalog[resolved_field]

        # 4. Geometric Guard: Strict dimension alignment verification
        if len(query_vector) != target_specs.dimension:
            raise VectorDimensionMismatchError(
                f"Expected {target_specs.dimension} dimensions, got {len(query_vector)}"
            )

        # 5. Build standard RedisVL query object.
        # RedisVL automatically forces the target key to 'vector_distance' under the hood.
        query = VectorQuery(
            vector=query_vector,
            vector_field_name=resolved_field,
            num_results=limit,
            filter_expression=filter_expression
        )

        # 5. Execute network round-trip through RedisDriver
        results = self.search_index.query(query)

        # 7. Short-circuit Guard, no need to parse an empty result
        if not results or len(results) == 0:
            return []

        # 8. Parse and clean results by binding the resolved field configuration
        return self._parse_and_clean_results(results, response_model, resolved_field=resolved_field)



    def _validate_and_resolve_vector_field(self, vector_field: Optional[str]) -> str:
        """Enforces runtime validation rules on the requested vector field.

        Ensures full geometric safety by rejecting ambiguities and missing fields
        before engaging network I/O operations (Fail-Fast).
        """
        # Rule 1: No vector_field supplied
        if vector_field is None:
            if len(self.catalog) == 1:
                return next(iter(self.catalog.keys()))

            # Crash immediately to prevent querying the wrong tensor layout
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

        # Rule 3: Everything is OK, let the execution proceed down the pipeline
        return vector_field

    def _parse_and_clean_results(self, results: Sequence[Any], response_model: Type[T], resolved_field: str) -> list[T]:
        """Filters tensor data, strips database technicalities, and computes a universal normalized similarity.

        Strict EAFP implementation. Any schema mismatch or database corruption triggers an immediate failure.
        """
        parsed_models = []

        # Retrieve specifications tied strictly to the queried vector field (Supports multi-vector contexts)
        specs = self.catalog[resolved_field]
        metric = specs.metric.upper()

        for doc in results:
            raw_distance = float(doc.vector_distance)

            # Production Geometric Guard: Unconditionally trap IEEE 754 NaN or Inf values
            # Ignore this document, distance is an aberration, but log it for observability.
            if math.isnan(raw_distance) or math.isinf(raw_distance):
                logger.warning(
                    f"Evicting document '{doc.id}' from result pool "
                    f"due to critical IEEE 754 geometric anomaly (distance: {raw_distance})."
                )
                continue

            match metric:
                case "COSINE" | "IP":
                    # 1. Macro-boundary verification to filter real severe anomalies (e.g. data corruption)
                    if raw_distance < -0.001 or raw_distance > 2.001:
                        logger.warning(
                            f"Evicting document '{doc.id}' from result pool. "
                            f"Out of bounds {metric} distance detected: {raw_distance}"
                        )
                        continue

                    # 2. Hardware-level clamping: absorbs floating-point approximations (e.g. 2.000000004 -> 2.0)
                    clamped_distance = max(0.0, min(2.0, raw_distance))
                    normalized_similarity = 1.0 - (clamped_distance / 2.0)

                case "L2":
                    # L2 space starts at 0.0 but mathematically has no upper bound
                    if raw_distance < -0.001:
                        logger.warning(
                            f"Evicting document '{doc.id}' from result pool. "
                            f"Impossible negative L2 distance: {raw_distance}"
                        )
                        continue

                    clamped_distance = max(0.0, raw_distance)
                    normalized_similarity = 1.0 / (1.0 + clamped_distance)

                case _:
                    raise RuntimeError(f"Unsupported database metric: {metric}")

            # Extract the raw dynamic fields dictionary from the Document instance,
            # clearing database internal metadata and the technical distance score.
            cleaned_doc = {
                k: v for k, v in doc.__dict__.items()
                if k not in self.catalog and k != "vector_distance"
            }

            # Inject the universal similarity baseline (0.0 to 1.0) expected by the Domain schema
            cleaned_doc["normalized_similarity"] = normalized_similarity

            # Pydantic model instantiates and fires its `@computed_field`.
            parsed_models.append(response_model.model_validate(cleaned_doc))

        return parsed_models

    @property
    def catalog(self) -> dict[str, VectorFieldSpecs]:
        """
        Expose the vector fields specifications catalog.
        Provides downstream components with read-only access to geometric specs.
        """
        return self._catalog

    @property
    def available_vector_fields(self) -> set[str]:
        """Returns the exact list of string keys available to use in 'vector_field'."""
        return set(self._catalog.keys())
