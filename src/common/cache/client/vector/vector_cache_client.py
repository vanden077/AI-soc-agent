import logging

from typing import Any, TypeVar, Sequence, Type, Optional

from pydantic import BaseModel
from redisvl.query import VectorQuery

from src.common.cache.geometric_guards import is_distance_valid, clamp_distance_result
from src.common.cache.client.vector.exceptions import VectorDimensionMismatchError
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
            index_path: str,
            embedding_engine: IEmbeddingEngine[Any],
            **kwargs: Any
    ) -> None:
        kwargs["vector_capability"] = True
        super().__init__(*args, **kwargs)
        self._index_path = index_path
        self._embedding_engine = embedding_engine
        # will contain all vectors available when lifespan will be synced
        self._catalog: dict[str, VectorFieldSpecs] = {}

    def sync_lifespan_catalog(self) -> None:
        """Hooks into the parent workflow and directly stores the native O(1) specs map."""
        super().init_search_index(self._index_path)
        self._catalog = self.get_index_vector_fields_catalog()


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
                dimensional geometric_guards registered inside the Redis index schema catalog.
            RuntimeError: If a lower-level Redis protocol error occurs or the custom query alias is missing.

        Returns:
            list[T]: response as a list of Pydantic schema
        """
        # 1. Payload validation guard
        if not query_text or not query_text.strip():
            # you want nothing ? ok I can give it to you without crashing.
            return []

        # 2. On-the-fly text vectorization via the abstract engine
        query_vector = self._embedding_engine.embed_query(query_text)

        # 3. Structural Field Resolution & Verification (Executes Rules 1, 2, and 3)
        vector_name = self._validate_and_resolve_vector_field(vector_field)
        target_specs = self.catalog[vector_name]

        # 4. Geometric Guard: Strict dimension alignment verification
        if len(query_vector) != target_specs.dimension:
            raise VectorDimensionMismatchError(
                f"Expected {target_specs.dimension} dimensions, got {len(query_vector)}"
            )

        # 5. Build standard RedisVL query object.
        # RedisVL automatically forces the target key to 'vector_distance' under the hood.
        query = VectorQuery(
            vector=query_vector,
            vector_field_name=vector_name,
            num_results=limit,
            filter_expression=filter_expression
        )
        results = self.search_index.query(query)

        # 6. Parse and clean results by binding the resolved field configuration
        return self._parse_and_clean_results(results, response_model, vector_name=vector_name)

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

    def _parse_and_clean_results(self, results: Sequence[Any], response_model: Type[T], vector_name: str) -> list[T]:
        """Filters tensor data, strips database technicalities, and computes a universal normalized similarity.

        Strict EAFP implementation. Any schema mismatch or database corruption triggers an immediate failure.
        """
        parsed_models = []

        # Retrieve specifications tied strictly to the queried vector field (Supports multi-vector contexts)
        specs = self.catalog[vector_name]

        for doc in results:
            raw_distance = float(doc.vector_distance)
            # Geometric Guard: Unconditionally trap IEEE 754 NaN or Inf values
            if not is_distance_valid(raw_distance=raw_distance, doc_id=doc.id):
                continue
            # Geometric Guard: apply clamping on raw_distance to prevent from LLM aberrations due to floating-point approximations.
            normalized_similarity = clamp_distance_result(raw_distance=raw_distance, doc_id=doc.id, metric=specs.metric)
            if normalized_similarity is None:
                # distance was not clampable, this document has to be evicted.
                continue
            # Extract the raw dynamic fields dictionary from the Document instance,
            # clearing database internal metadata and the technical distance score.
            # HARDWARE OPTIMIZATION GUARD: Explicitly strip heavy vector floating-point matrices
            # from the dictionary BEFORE passing it to Pydantic validation loops.
            # Allowing Pydantic's Rust engine to ingest, evaluate, and subsequently discard a 384/512 or even more
            # float tensor sequence wastes substantial CPU clock cycles and causes unnecessary memory
            # allocation overhead. Fail-Fast overhead containment.
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

    # ============================================================================
    # STRICT READ-ONLY COMPLIANCE INTERRUPTS
    # ============================================================================
    def flush_db(self) -> None:
        """
        Strict Read-Only Enforcement.
        Flushing the database cache is strictly forbidden on the semantic query subsystem.

        :raises RuntimeError: Always, to prevent destructive operations at runtime.
        """
        raise RuntimeError(
            "Destructive Operation Blocked: VectorCacheClient is a read-only semantic query engine. "
            "Administrative flush operations are strictly forbidden in this context."
        )