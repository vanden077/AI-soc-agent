import logging
from typing import Any

import pytest
from unittest.mock import patch, PropertyMock, MagicMock
from pydantic import BaseModel, computed_field

from src.persistence.engine.redis.client.vector.exceptions import VectorDimensionMismatchError
from src.persistence.engine.redis.client.vector.vector_cache_client import VectorCacheClient
from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.engine.redis.driver.vector_fields_specs import VectorFieldSpecs


# ============================================================================
# LOCAL FIXTURES
# ============================================================================
@pytest.fixture(scope="function")
def vector_cache(redis_driver_factory, mock_redis_vl_search_index: MagicMock):
    """Instantiate VectorCacheClient backed by an isolated FakeRedis driver."""
    driver = redis_driver_factory(
        decode_responses=False,
        ssl=False,
        db=1,
        vector_capability=True,
    )
    driver.init_pool()
    client = VectorCacheClient(driver=driver, index_path="mitre_attack_v1")

    with patch.object(
        RedisDriver,
        "search_index",
        new_callable=PropertyMock,
        return_value=mock_redis_vl_search_index,
    ):
        yield client


class DummyResponseModel(BaseModel):
    """Target Pydantic model to validate record parsing."""
    id: str
    raw_content: str
    normalized_similarity: float

    @computed_field
    @property
    def confidence_score(self) -> float:
        return round(self.normalized_similarity * 5.0, 2)


# ============================================================================
# LIFESPAN SYNCHRONIZATION & O(1) CATALOG MOUNT
# ============================================================================

def test_sync_lifespan_catalog_success(vector_cache: VectorCacheClient):
    """
    Given a valid RedisVL search index,
    When synchronizing the client lifespan during boot via sync_lifespan_catalog,
    Then it must invoke parent binding and successfully mount the local O(1) specs catalog.
    """
    vector_cache.sync_lifespan_catalog()
    assert len(vector_cache.catalog) == 2
    assert "text_embedding" in vector_cache.catalog
    assert "image_embedding" in vector_cache.catalog
    assert isinstance(vector_cache.catalog["text_embedding"], VectorFieldSpecs)
    assert isinstance(vector_cache.catalog["image_embedding"], VectorFieldSpecs)


def test_sync_lifespan_catalog_critical_failure(vector_cache: VectorCacheClient):
    """
    Given an invalid or corrupted index schema layout causing a parent parsing crash,
    When synchronizing the catalog during lifespan initialization,
    Then it must propagate the exception to guarantee a fast-fail application crash.
    """
    with patch.object(RedisDriver, "get_index_vector_fields_catalog", side_effect=ValueError("Schema corrupted")):
        with pytest.raises(ValueError, match="Schema corrupted"):
            vector_cache.sync_lifespan_catalog()


# ============================================================================
# TEST FIELD VALIDATION & RESOLUTION
# ============================================================================

def test_validate_and_resolve_vector_field_rule_1_implicit_success(vector_cache: VectorCacheClient):
    """
    Given a catalog discovered with exactly one unique vector field path,
    When calling field resolution with None,
    Then it must automatically fall back and return that unique field name.
    """
    single_field_catalog = {"text_embedding": VectorFieldSpecs(
        name="text_embedding",
        dimension=384,
        metric="cosine",
        algorithm="hnsw",
        source_path="$.payload.text_embedding"
        )
    }
    with patch.object(RedisDriver, "get_index_vector_fields_catalog", return_value=single_field_catalog):
        vector_cache.sync_lifespan_catalog()

    resolved = vector_cache._validate_and_resolve_vector_field(None)
    assert resolved == "text_embedding"


def test_validate_and_resolve_vector_field_rule_1_ambiguity_raises_value_error(
        vector_cache: VectorCacheClient
):
    """
    Given a multi-tensor catalog layout (multiple vector fields discovered during lifespan),
    When calling field resolution with None,
    Then it must fail-fast immediately by raising a descriptive ValueError.
    """
    vector_cache.sync_lifespan_catalog()

    with pytest.raises(
            ValueError,
            match="Ambiguity in vector search: Multiple vector fields are configured"
    ) as exc_info:
        vector_cache._validate_and_resolve_vector_field(None)

    assert "text_embedding" in str(exc_info.value)
    assert "image_embedding" in str(exc_info.value)


def test_validate_and_resolve_vector_field_rule_2_not_in_catalog_raises_value_error(
    vector_cache: VectorCacheClient
):
    """
    Given an explicit vector field token,
    When that specific token does not match any key inside the active catalog,
    Then it must raise a dedicated configuration ValueError listing valid choices.
    """
    vector_cache.sync_lifespan_catalog()

    with pytest.raises(
            ValueError,
            match="Configuration Error: The requested vector field 'unknown_embedding' does not exist"
    ) as exc_info:
        vector_cache._validate_and_resolve_vector_field("unknown_embedding")

    assert "text_embedding" in str(exc_info.value)
    assert "image_embedding" in str(exc_info.value)

def test_validate_and_resolve_vector_field_rule_3_explicit_success(
    vector_cache: VectorCacheClient
):
    """
    Given a multi-tensor catalog environment,
    When target field parameter matches a valid existing catalog key explicitly,
    Then it must pass verification smoothly and return the input string unmodified.
    """
    vector_cache.sync_lifespan_catalog()
    resolved = vector_cache._validate_and_resolve_vector_field("image_embedding")
    assert resolved == "image_embedding"

# ============================================================================
# TEST PARSE AND CLEAN REDIS VL DOCUMENTS BEFORE PYDANTIC SERIALIZATION
# ============================================================================
@pytest.mark.parametrize(
    "redis_vl_doc_result, vector_name, should_parser_accept_it, log_should_contain",
    [
        ({"id": "rec_nan", "raw_content": "Corrupted NaN", "vector_distance": float("nan")}, "text_embedding", False, "due to critical IEEE 754 geometric anomaly (distance: "),
        ({"id": "rec_inf", "raw_content": "Corrupted Inf", "vector_distance": float("inf")}, "text_embedding", False, "due to critical IEEE 754 geometric anomaly (distance: "),
        ({"id": "rec_severe_negative", "raw_content": "Anomaly Low", "vector_distance": -0.05}, "text_embedding", False, "Out of bounds COSINE distance detected"),
        ({"id": "rec_severe_positive", "raw_content": "Anomaly High", "vector_distance": 2.1}, "text_embedding", False, "Out of bounds COSINE distance detected"),
        ({"id": "rec_severe_negative_l2", "raw_content": "Impossible L2", "vector_distance": -0.5}, "image_embedding", False, "Impossible negative L2 distance"),
        ({"id": "rec_valid", "raw_content": "Valid Entry", "vector_distance": 0.4}, "text_embedding", True, ""),
        ({"id": "rec_micro_low", "raw_content": "Micro Negative Match", "vector_distance": -0.0004}, "text_embedding", True, ""),
        ({"id": "rec_micro_high", "raw_content": "Micro Positive Match", "vector_distance": 2.0003}, "text_embedding", True, ""),
        ({"id": "rec_nominal_l2", "raw_content": "Perfect Spatial Match", "vector_distance": 0.0}, "image_embedding", True, ""),
        ({"id": "rec_l2_noise", "raw_content": "Micro Negative Noise", "vector_distance": -0.0004}, "image_embedding", True, ""),
        ({"id": "rec_l2_far", "raw_content": "Large Distance 9", "vector_distance": 9.0}, "image_embedding", True, "")
    ],
    ids=[
        "evict_nan",
        "evict_inf",
        "evict_rec_severe_negative",
        "evict_rec_severe_positive",
        "evict_rec_severe_negative_l2",
        "accept_valid",
        "accept_rec_micro_low",
        "accept_rec_micro_high",
        "accept_rec_nominal_l2",
        "accept_rec_l2_micro_low",
        "accept_rec_l2_large_distance"
    ]
)
def test_parse_and_clean_results(
        vector_cache: VectorCacheClient,
        caplog,
        redis_vl_doc_result: dict[str, Any],
        vector_name: str,
        should_parser_accept_it: bool,
        log_should_contain: str
):
    """
    Given a Redis document.
    Check document is evicted and logged, or normalized correctly.
    """
    vector_cache.sync_lifespan_catalog()

    # tmp config to capture logs at warning level
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=[redis_vl_doc_result],
            response_model=DummyResponseModel,
            vector_name=vector_name # text_embedding = COSINE, image_embedding = L2
        )

    if should_parser_accept_it:
        # document not evicted ?
        assert len(parsed_output) == 1
    else:
        # document evicted ?
        assert len(parsed_output) == 0
        # are aberrations correctly logged ?
        assert len(caplog.records) == 1
        assert log_should_contain in caplog.text
        # are evicted documents clearly identified ?
        assert redis_vl_doc_result["id"] in caplog.text

def test_parse_and_clean_results_unsupported_metric_raises_runtime_error(
        vector_cache: VectorCacheClient
):
    """
    Given an index configuration mounted with an unsupported vector metric,
    When attempting to parse query results through the match/case architecture,
    Then it must fail-fast and raise a descriptive RuntimeError.
    """
    exotic_spec = VectorFieldSpecs(
        name="exotic_embedding",
        dimension=384,
        metric="IM_TIRED",  # unknown metric should raise Runtime exception
        algorithm="hnsw",
        source_path="$.payload.exotic_embedding"
    )

    with patch.object(RedisDriver, "get_index_vector_fields_catalog", return_value={"exotic_embedding": exotic_spec}):
        vector_cache.sync_lifespan_catalog()

    # Create a fake document making parser crash
    results = [{"id": "rec_exotic", "name": "Exotic Metric Entry", "vector_distance": 0.5}]

    with pytest.raises(RuntimeError, match="Unsupported database structural index metric: IM_TIRED"):
        vector_cache._parse_and_clean_results(
            results=results,
            response_model=DummyResponseModel,
            vector_name="exotic_embedding"
        )

# ============================================================================
# TEST SIMILARITY SEARCH
# ============================================================================

def test_similarity_search_nominal_happy_path_orchestration_success(vector_cache: VectorCacheClient, sample_query_vector):
    """
    Given a valid input query text and pristine active catalog specifications,
    When executing a similarity search flow completely,
    Then it must vectorise on-the-fly, build a proper RedisVL VectorQuery,
    and output domain Pydantic models with their computed business score.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 2 documents returned by search_index.query
    mocked_db_documents = [
        {"id": "doc_meta_001", "raw_content": "Architecture Document", "vector_distance": 0.2},
        {"id": "doc_meta_002", "raw_content": "FastAPI Cache Framework", "vector_distance": 0.8}
    ]

    vector_cache._driver.search_index.query.return_value = mocked_db_documents

    # Test now
    results = vector_cache.similarity_search(
        query_vector=sample_query_vector,
        response_model=DummyResponseModel,
        vector_field="text_embedding",  # COSINE
        limit=2
    )

    # All documents stays into the list ?
    assert len(results) == 2

    # First document (Cosine distance is 0.2)
    # normalized similarity : 1.0 - (0.2 / 2.0) = 0.9
    # Pydantic confidence score : round(0.9 * 5.0, 2) = 4.5/5.0
    assert results[0].id == "doc_meta_001"
    assert results[0].raw_content == "Architecture Document"
    assert results[0].normalized_similarity == 0.9
    assert results[0].confidence_score == 4.5

    # Second document (Cosine distance is 0.8)
    # normalized similarity : 1.0 - (0.8 / 2.0) = 0.6
    # Pydantic confidence score : round(0.6 * 5.0, 2) = 3.0/5.0
    assert results[1].id == "doc_meta_002"
    assert results[1].raw_content == "FastAPI Cache Framework"
    assert results[1].normalized_similarity == 0.6
    assert results[1].confidence_score == 3.0

    # Check request is sent to RedisVl
    vector_cache._driver.search_index.query.assert_called_once()


@pytest.mark.parametrize("invalid_vector", [[], None])
def test_similarity_search_payload_guard_returns_empty_list(
    vector_cache: VectorCacheClient,
    invalid_vector: Any
):
    """
    Given an empty, blank, or None query text,
    When calling similarity_search,
    Then it must gracefully return an empty list immediately without raising errors.
    """
    results = vector_cache.similarity_search(
        query_vector=invalid_vector,
        response_model=DummyResponseModel
    )
    assert results == []

def test_similarity_search_dimension_mismatch_raises_vector_dimension_mismatch_error(vector_cache: VectorCacheClient):
    """
    Given a query vector returned by the engine with an incorrect layout dimension,
    When comparing its length against the rigid catalog specifications,
    Then it must fail-fast and raise a VectorDimensionMismatchError.
    """
    vector_cache.sync_lifespan_catalog()
    with pytest.raises(VectorDimensionMismatchError, match="Expected 384 dimensions, got 3"):
        vector_cache.similarity_search(
            query_vector=[0.1, 0.2, 0.3],
            response_model=DummyResponseModel,
            vector_field="text_embedding"
        )

def test_metadata_fields_property_exposes_synced_fields(vector_cache: VectorCacheClient) -> None:
    """Verify metadata_fields property exposes the non-vector fields extracted during sync."""
    vector_cache.sync_lifespan_catalog()
    assert vector_cache.metadata_fields == {"id", "raw_content"}

def test_resolve_return_fields_raises_when_zero_fields_overlap(vector_cache: VectorCacheClient) -> None:
    """Verify _resolve_return_fields raises ValueError when none of the model fields exist in index metadata."""
    vector_cache.sync_lifespan_catalog()

    class UnrelatedModel(BaseModel):
        unknown_a: str
        unknown_b: int

    with pytest.raises(ValueError, match="Schema Mismatch Error"):
        vector_cache._resolve_return_fields(UnrelatedModel)

def test_build_tag_filter_combines_multiple_tags() -> None:
    """Verify _build_tag_filter builds a combined RedisVL FilterExpression for multi-key metadata filters."""
    expr = VectorCacheClient._build_tag_filter({"platforms": "windows", "tactic": "execution"})
    assert expr is not None
    assert "platforms" in str(expr)
    assert "tactic" in str(expr)

def test_vector_cache_health_delegates_to_driver(vector_cache: VectorCacheClient) -> None:
    """Verify health() delegates directly to the underlying driver."""
    with patch.object(vector_cache._driver, "health", return_value=True) as mock_health:
        assert vector_cache.health() is True
        mock_health.assert_called_once()

def test_vector_cache_close_delegates_to_driver(vector_cache: VectorCacheClient) -> None:
    """Verify close() delegates connection pool shutdown directly to the underlying driver."""
    with patch.object(vector_cache._driver, "close") as mock_close:
        vector_cache.close()
        mock_close.assert_called_once()
