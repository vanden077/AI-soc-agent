import logging
from typing import Any

import pytest
from unittest.mock import patch
from pydantic import BaseModel, computed_field

from src.common.cache.client.vector.exceptions import EmptyVectorError, VectorDimensionMismatchError
from src.common.cache.driver.redis_driver import RedisDriver
from src.common.cache.driver.vector_fields_specs import VectorFieldSpecs
from src.common.cache import VectorCacheClient


# ============================================================================
# TEST MODELS
# ============================================================================

class DummyResponseModel(BaseModel):
    """Target Pydantic model to validate record parsing."""
    id: str
    name: str
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

def test_parse_and_clean_results_step_1_evicts_ieee754_anomalies_and_logs(
        vector_cache: VectorCacheClient,
        redis_doc_factory,
        caplog
):
    """
    I know this test and next one could be parametrized. But think about readability.
    Given a pool of Redis documents containing IEEE 754 anomalies (NaN and Inf),
    When step 1 geometric guard encounters them during parsing,
    Then it must silently evict the corrupted records, log a warning, and keep valid entries.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 3 fake documents, 2 will be ejected and only one is valid.
    mixed_results = redis_doc_factory([
        {"id": "rec_nan", "name": "Corrupted NaN", "vector_distance": float("nan")},
        {"id": "rec_inf", "name": "Corrupted Inf", "vector_distance": float("inf")},
        {"id": "rec_valid", "name": "Valid Entry", "vector_distance": 0.4}
    ])

    # tmp config to capture logs at warning level
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=mixed_results,
            response_model=DummyResponseModel,
            resolved_field="text_embedding" # COSINE
        )

    # only one document remaining ?
    assert len(parsed_output) == 1
    # is it the awaited document ?
    assert parsed_output[0].id == "rec_valid"
    # is the normalized similarity ok to be sent to Pydantic ?
    assert parsed_output[0].normalized_similarity == 0.8  # 1.0 - (0.4 / 2.0)

    # are aberrations correctly logged ?
    assert len(caplog.records) == 2
    # is the log clearly indicating why the document has been evicted ?
    assert "critical IEEE 754 geometric anomaly" in caplog.text
    # are evicted documents clearly identified ?
    assert "rec_nan" in caplog.text
    assert "rec_inf" in caplog.text


def test_parse_and_clean_results_step_2_evicts_severe_out_of_bounds_cosine_and_logs(
        vector_cache: VectorCacheClient,
        redis_doc_factory,
        caplog
):
    """
    I know this test and previous one could be parametrized. But think about readability.
    Given a pool of Redis documents with severe out-of-bounds Cosine distances,
    When parsing the result pool under angular metrics,
    Then it must log a warning, discard the anomalies, and preserve valid records.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 3 fake documents, 2 will be ejected and only one is valid.
    mixed_results = redis_doc_factory([
        {"id": "rec_severe_negative", "name": "Anomaly Low", "vector_distance": -0.05},
        {"id": "rec_severe_positive", "name": "Anomaly High", "vector_distance": 2.1},
        {"id": "rec_nominal_valid", "name": "Valid Entry", "vector_distance": 1.0}
    ])

    # tmp config to capture logs at warning level
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=mixed_results,
            response_model=DummyResponseModel,
            resolved_field="text_embedding" # COSINE
        )

    # only one document remaining ?
    assert len(parsed_output) == 1
    # is it the awaited document ?
    assert parsed_output[0].id == "rec_nominal_valid"
    # is the normalized similarity ok to be sent to Pydantic ?
    assert parsed_output[0].normalized_similarity == 0.5  # 1.0 - (1.0 / 2.0)

    # are aberrations correctly logged ?
    assert len(caplog.records) == 2
    # is the log clearly indicating why the document has been evicted ?
    assert "Out of bounds COSINE distance detected" in caplog.text
    # are evicted documents clearly identified ?
    assert "rec_severe_negative" in caplog.text
    assert "rec_severe_positive" in caplog.text


def test_parse_and_clean_results_step_3_clamps_micro_approximations_cosine(
        vector_cache: VectorCacheClient,
        redis_doc_factory,
        caplog
):
    """
    I know, did i already told you about readability ? :)
    Given a pool of Redis documents with micro floating-point approximations,
    When parsing the results under angular metrics,
    Then it must preserve the records, clamp them safely, and calculate bounded similarities.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 2 fake documents with acceptable micro approximations
    micro_results = redis_doc_factory([
        {"id": "rec_micro_low", "name": "Micro Negative Match", "vector_distance": -0.0004},
        {"id": "rec_micro_high", "name": "Micro Positive Match", "vector_distance": 2.0003}
    ])

    # tmp config to capture logs at warning level (no logs should be emitted)
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=micro_results,
            response_model=DummyResponseModel,
            resolved_field="text_embedding" # COSINE
        )

    # all documents accepted ?
    assert len(parsed_output) == 2

    # Check clamping
    # -0.0004 becomes 0.0, then => 1.0 - (0.0 / 2.0) = 1.0
    assert parsed_output[0].id == "rec_micro_low"
    assert parsed_output[0].normalized_similarity == 1.0

    # Check clamping
    # 2.0003 becomes 2.0, then => 1.0 - (2.0 / 2.0) = 0.0
    assert parsed_output[1].id == "rec_micro_high"
    assert parsed_output[1].normalized_similarity == 0.0

    # Assert that no log are emitted
    assert len(caplog.records) == 0


def test_parse_and_clean_results_step_4_evicts_severe_negative_l2_and_logs(
        vector_cache: VectorCacheClient,
        redis_doc_factory,
        caplog
):
    """
    If you have any questions about pytest parametrization, please read previous tests...
    Given a pool of Redis documents containing a severe negative L2 distance,
    When parsing the result pool under spatial metrics,
    Then it must log a warning, discard the geometric anomaly, and preserve valid records.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 2 fake documents, 1 have to be ejected, not the other one.
    mixed_results = redis_doc_factory([
        {"id": "rec_severe_negative_l2", "name": "Impossible L2", "vector_distance": -0.5},
        {"id": "rec_nominal_l2", "name": "Perfect Spatial Match", "vector_distance": 0.0}
    ])

    # tmp config to capture logs at warning level
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=mixed_results,
            response_model=DummyResponseModel,
            resolved_field="image_embedding" # L2
        )

    # only one document remaining ?
    assert len(parsed_output) == 1
    # is it the awaited document ?
    assert parsed_output[0].id == "rec_nominal_l2"
    # is the normalized similarity ok to be sent to Pydantic ?
    assert parsed_output[0].normalized_similarity == 1.0

    # are aberrations correctly logged ?
    assert len(caplog.records) == 1
    # is the log clearly indicating why the document has been evicted ?
    assert "Impossible negative L2 distance" in caplog.text
    # is evicted document clearly identified ?
    assert "rec_severe_negative_l2" in caplog.text


def test_parse_and_clean_results_step_5_clamps_and_calculates_decay_l2(
        vector_cache: VectorCacheClient,
        redis_doc_factory,
        caplog
):
    """
    Readability... Do you prefer a melt of conditions or a targeted test ?
    Given a pool of Redis documents with micro-negative L2 noise or typical positive distances,
    When parsing the results under spatial metrics,
    Then it must clamp sub-zero noise to 0.0 and project distances onto a valid 0 to 1 decay curve.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 3 fakes valid documents
    spatial_results = redis_doc_factory([
        {"id": "rec_l2_noise", "name": "Micro Negative Noise", "vector_distance": -0.0004},
        {"id": "rec_l2_mid", "name": "Standard Distance 1", "vector_distance": 1.0},
        {"id": "rec_l2_far", "name": "Large Distance 9", "vector_distance": 9.0}
    ])

    # tmp config to capture logs at warning level (no logs should be emitted)
    with caplog.at_level(logging.WARNING):
        parsed_output = vector_cache._parse_and_clean_results(
            results=spatial_results,
            response_model=DummyResponseModel,
            resolved_field="image_embedding" # L2
        )

    # All documents stays into the list ?
    assert len(parsed_output) == 3
    # No logs emitted ?
    assert len(caplog.records) == 0

    # Check clamping document 1
    # -0.0004 becomes 0.0, then => 1.0 / (1.0 + 0.0) = 1.0
    assert parsed_output[0].id == "rec_l2_noise"
    assert parsed_output[0].normalized_similarity == 1.0

    # Check no clamping for document 2
    # Distance 1.0 -> 1.0 / (1.0 + 1.0) = 0.5
    assert parsed_output[1].id == "rec_l2_mid"
    assert parsed_output[1].normalized_similarity == 0.5

    # Check no clamping for document 3
    # Distance 9.0 -> 1.0 / (1.0 + 9.0) = 0.1
    assert parsed_output[2].id == "rec_l2_far"
    assert parsed_output[2].normalized_similarity == 0.1


def test_parse_and_clean_results_step_6_unsupported_metric_raises_runtime_error(
        vector_cache: VectorCacheClient,
        redis_doc_factory
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
    results = redis_doc_factory([
        {"id": "rec_exotic", "name": "Exotic Metric Entry", "vector_distance": 0.5}
    ])

    with pytest.raises(RuntimeError, match="Unsupported database metric: IM_TIRED"):
        vector_cache._parse_and_clean_results(
            results=results,
            response_model=DummyResponseModel,
            resolved_field="exotic_embedding"
        )

# ============================================================================
# TEST SIMILARITY SEARCH
# ============================================================================

def test_similarity_search_nominal_happy_path_orchestration_success(
        vector_cache: VectorCacheClient,
        redis_doc_factory
):
    """
    Given a valid input query text and pristine active catalog specifications,
    When executing a similarity search flow completely,
    Then it must vectorise on-the-fly, build a proper RedisVL VectorQuery,
    and output domain Pydantic models with their computed business score.
    """
    vector_cache.sync_lifespan_catalog()

    # Create 2 documents returned by search_index.query
    mocked_db_documents = redis_doc_factory([
        {"id": "doc_meta_001", "name": "Architecture Document", "vector_distance": 0.2},
        {"id": "doc_meta_002", "name": "FastAPI Cache Framework", "vector_distance": 0.8}
    ])

    vector_cache.search_index.query.return_value = mocked_db_documents

    # Test now
    results = vector_cache.similarity_search(
        query_text="hello, im looking for something but i dont know what.",
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
    assert results[0].name == "Architecture Document"
    assert results[0].normalized_similarity == 0.9
    assert results[0].confidence_score == 4.5

    # Second document (Cosine distance is 0.8)
    # normalized similarity : 1.0 - (0.8 / 2.0) = 0.6
    # Pydantic confidence score : round(0.6 * 5.0, 2) = 3.0/5.0
    assert results[1].id == "doc_meta_002"
    assert results[1].name == "FastAPI Cache Framework"
    assert results[1].normalized_similarity == 0.6
    assert results[1].confidence_score == 3.0

    # Check request is sent to RedisVl
    vector_cache.search_index.query.assert_called_once()


@pytest.mark.parametrize("invalid_text", ["", "   ", None])
def test_similarity_search_payload_guard_returns_empty_list(
    vector_cache: VectorCacheClient,
    invalid_text: Any
):
    """
    Given an empty, blank, or None query text,
    When calling similarity_search,
    Then it must gracefully return an empty list immediately without raising errors.
    """
    results = vector_cache.similarity_search(
        query_text=invalid_text,
        response_model=DummyResponseModel
    )
    assert results == []


def test_similarity_search_empty_database_results_returns_empty_list(vector_cache: VectorCacheClient):
    """
    Given a valid query,
    When the database returns zero matching records (empty result list),
    Then the client must short-circuit and return an empty list without invoking the parser.
    """
    vector_cache.sync_lifespan_catalog()

    # No match in DB
    vector_cache.search_index.query.return_value = []

    with patch.object(vector_cache, "_parse_and_clean_results",
                      wraps=vector_cache._parse_and_clean_results) as spy_parser:
        results = vector_cache.similarity_search(
            query_text="Valid text but no matches in DB",
            response_model=DummyResponseModel,
            vector_field="text_embedding"
        )

    assert results == []
    # assert that _parse_and_clean_results has not been called
    spy_parser.assert_not_called()


def test_similarity_search_empty_vector_engine_anomaly_raises_exception(
        vector_cache: VectorCacheClient,
        mock_embedding_engine
):
    """
    Given a valid input query text,
    When the injected embedding engine returns an empty or null vector layout,
    Then it must fail fast and raise a dedicated EmptyVectorError.
    """
    vector_cache.sync_lifespan_catalog()

    # Embedding engine do not crash, but return an empty float list.
    mock_embedding_engine.embed_query.return_value = []

    # Act & Assert : L'exécution doit couper net avec l'exception dédiée
    with pytest.raises(EmptyVectorError, match="Vector cannot be empty"):
        vector_cache.similarity_search(
            query_text="Valid architectural prompt",
            response_model=DummyResponseModel,
            vector_field="text_embedding"
        )


def test_similarity_search_dimension_mismatch_raises_vector_dimension_mismatch_error(
        vector_cache: VectorCacheClient,
        mock_embedding_engine
):
    """
    Given a query vector returned by the engine with an incorrect layout dimension,
    When comparing its length against the rigid catalog specifications,
    Then it must fail-fast and raise a VectorDimensionMismatchError.
    """
    vector_cache.sync_lifespan_catalog()

    # Engine return only 3 dimensions instead of 384
    mock_embedding_engine.embed_query.return_value = [0.1, 0.2, 0.3]

    with pytest.raises(VectorDimensionMismatchError, match="Expected 384 dimensions, got 3"):
        vector_cache.similarity_search(
            query_text="Prompt pour tester le crash de dimension",
            response_model=DummyResponseModel,
            vector_field="text_embedding"
        )