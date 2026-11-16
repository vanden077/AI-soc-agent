import json
from typing import cast, Mapping, Any
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from src.persistence.engine.redis.client.vector.ingestion_cache_client import IngestionCacheClient
from src.persistence.engine.redis.driver.redis_driver import RedisDriver


# ============================================================================
# LOCAL FIXTURES
# ============================================================================
@pytest.fixture(scope="function")
def ingestion_cache(redis_driver_factory, mock_redis_vl_search_index: MagicMock):
    """Instantiate IngestionCacheClient backed by an isolated FakeRedis driver."""
    driver = redis_driver_factory(
        decode_responses=True,
        ssl=False,
        db=1,
        vector_capability=True,
    )
    driver.init_pool()
    client = IngestionCacheClient(
        driver=driver,
        target_vector_field="text_embedding",
        semantic_hashes_key="mitre:persistence:semantic_hashes",
    )

    with patch.object(
        RedisDriver,
        "search_index",
        new_callable=PropertyMock,
        return_value=mock_redis_vl_search_index,
    ):
        yield client

# ============================================================================
# TESTS
# ============================================================================
def test_init_search_index_nominal_hydration(ingestion_cache, mock_redis_vl_search_index):
    """
    Nominal Case: The search index loads successfully.
    The index prefix and target vector field name must be correctly extracted,
    formatted, and frozen into the client state.
    """
    # Given: The global conftest fixture exposes 'text_embedding' with type 'vector'
    # When
    ingestion_cache.init_search_index("mitre_attack_v1")
    # Then
    assert ingestion_cache.key_prefix == "mitre:"
    assert ingestion_cache.vector_field_name == "text_embedding"

def test_init_search_index_raises_value_error_on_mismatched_field(ingestion_cache, mock_redis_vl_search_index):
    """
    Edge Case: The parsed YAML schema is valid and contains vectors, but the developer
    configured the client with a target_vector_field name that does not exist in the schema.
    Must trigger an immediate Fail-Fast ValueError.
    """
    # Given: The YAML schema is perfectly valid (has text_embedding),
    # but we simulate a developer typo in the client's configuration
    ingestion_cache._target_vector_field = "invalid_typo_vector_name"

    # When & Then
    # The schema has 'text_embedding', but the client looks for 'invalid_typo_vector_name'
    with pytest.raises(ValueError) as err:
        ingestion_cache.init_search_index("mitre_attack_v1")
    assert str(err.value) == ("Invalid index schema layout: "
                              "The configured vector field 'invalid_typo_vector_name' "
                              "was not detected inside the unified catalog extracted from 'mitre_attack_v1'."
                              "Available vector fields defined in the schema are: ['text_embedding', 'image_embedding']")

def test_fetch_remote_hashes_success(ingestion_cache):
    """
    Nominal Case: Successfully query the centralized signature registry key.
    Must verify that data written to the fake persistence server is accurately retrieved
    as decoded strings in a single syscall.
    """
    # Given: Populate the fake in-memory Redis database directly
    target_key = "mitre:persistence:semantic_hashes"
    mock_fingerprints = {"T1055": "hash_v1", "T1055.001": "hash_sub_v1"}
    ingestion_cache._driver.redis_client.hset(target_key, mapping=cast(Mapping[Any, Any], mock_fingerprints))

    # When: Invoke the production function
    registry = ingestion_cache.fetch_remote_hashes()
    # Then: Verify state consistency and clean string decoding
    assert registry == mock_fingerprints

def test_fetch_remote_hashes_fail_safe_on_exception(mocker, caplog):
    """
    Edge Case: Redis infrastructure experiences a critical execution failure.
    The client must capture the exception, log the diagnostic context,
    and safely degrade to an empty map to let the warm-up sequence continue.
    """
    # Given: A mocked driver whose redis_client raises a network exception
    mock_driver = mocker.MagicMock()
    mock_driver.redis_client.hgetall.side_effect = Exception("Redis network timeout")
    client = IngestionCacheClient(
        driver=mock_driver,
        target_vector_field="text_embedding",
        semantic_hashes_key="mitre:persistence:semantic_hashes",
    )

    # When
    registry = client.fetch_remote_hashes()

    # Then: Must return a safe empty fallback block and issue an error log
    assert registry == {}
    assert "Failed to synchronize fingerprints: Redis network timeout" in caplog.text


def test_set_remote_hashes_success(ingestion_cache):
    """
    Nominal Case: Successfully persist a batch of fingerprints map into Redis.
    Must verify that signatures are correctly written into the single Hash key
    on the fake server.
    """
    # Given
    target_key = "mitre:persistence:semantic_hashes"
    batch_signatures = {"T1055": "hash_v2", "T1027": "hash_v1"}

    # When: Flush the signatures through the production code
    ingestion_cache.set_remote_hashes(batch_signatures)
    # Then: Read directly from FakeRedis to confirm persistence state
    stored_hashes = ingestion_cache._driver.redis_client.hgetall(target_key)
    assert stored_hashes == batch_signatures


def test_set_remote_hashes_escalates_runtime_error_on_exception(mocker, caplog):
    """
    Edge Case: Redis architecture triggers an execution error (e.g., Out Of Memory).
    The client must log the exact error message and escalate the incident into
    an explicit RuntimeError to block the pipeline from corrupting the delta-persistence.
    """
    # Given: A mocked driver whose redis_client raises an infrastructure error
    mock_driver = mocker.MagicMock()
    mock_driver.redis_client.hset.side_effect = Exception("OOM Command not allowed")
    client = IngestionCacheClient(
        driver=mock_driver,
        target_vector_field="text_embedding",
        semantic_hashes_key="mitre:persistence:semantic_hashes",
    )
    batch_signatures = {"T1055": "hash_v2"}

    # When & Then: Enforce fast-failing error escalation contract
    with pytest.raises(RuntimeError) as err:
        client.set_remote_hashes(batch_signatures)
    assert "Infrastructure delta-cache persistence failure: OOM Command not allowed" in str(err.value)
    assert "Failed to insert documents fingerprints into 'mitre:persistence:semantic_hashes': OOM Command not allowed" in caplog.text

def test_normalize_document_types_strict_flattening_constraints(ingestion_cache):
    """
    Nominal Case: Agnostic structural formatting of Python primitives into flat
    Redis Hash compatible attributes.
    Must verify float arrays to Float32 bytes conversions, list flattening,
    and dictionary serialization while safeguarding source data immutability.
    """
    # Given: Bootstrap the client states natively using the conftest fixture defaults
    ingestion_cache.init_search_index("dummy_path.yaml")

    # An agnostic payload containing all polymorphic types that need flattening
    raw_generic_doc = {
        "id": "unique_id_123",
        "custom_tags": ["tag_a", "tag_b"],  # Python List -> Redis Tag string
        "nested_metadata": {"key": "value", "status": "active"},  # Python Dict -> JSON block
        "regular_text": "A standard untouched string attribute"  # Regular string -> untouched
    }
    dummy_float_vector = [0.25, 0.5, 0.75, -1.25]

    # When: Execute the mapping logic
    normalized_doc = ingestion_cache._normalize_document_types(raw_generic_doc, dummy_float_vector)

    # Then: Verify data transformations boundaries
    # 1. Vector float list must be packed into contiguous Float32 C-bytes array
    expected_vector_bytes = np.array(dummy_float_vector, dtype=np.float32).tobytes()
    assert normalized_doc["text_embedding"] == expected_vector_bytes

    # 2. Python lists must be mapped to comma-separated strings (Redis TAG field requirement)
    assert normalized_doc["custom_tags"] == "tag_a,tag_b"

    # 3. Polymorphic embedded dict maps must be flattened into valid JSON blocks
    expected_json_block = json.dumps(raw_generic_doc["nested_metadata"], ensure_ascii=False)
    assert normalized_doc["nested_metadata"] == expected_json_block

    # 4. Standard structural types should remain totally unaffected
    assert normalized_doc["id"] == "unique_id_123"
    assert normalized_doc["regular_text"] == raw_generic_doc["regular_text"]

    # 5. IMMUTABILITY SAFEGUARD: The business source container must not be mutated in place
    assert isinstance(raw_generic_doc["custom_tags"], list)
    assert "text_embedding" not in raw_generic_doc


def test_execute_bulk_upsert_coordinates_pipeline_load(ingestion_cache, mock_redis_vl_search_index):
    """
    Nominal Case: Coordinate the structural normalization loop over a batch
    and verify the bulk transmission to the underlying RedisVL SearchIndex container.
    """
    # Given: Initialize the client state natively
    ingestion_cache.init_search_index("dummy_path.yaml")

    # A minimal agnostic batch payload
    compiled_batch_payload = [
        {
            "id": "doc_unique_id",
            "categories": ["cyber", "threat"]
        }
    ]
    batch_embeddings: list[list[float | int]] = [[0.1, 0.2, 0.3]]

    # When: Execute the target bulk upsert operation
    ingestion_cache.execute_bulk_upsert(
        payload=compiled_batch_payload,
        embeddings=batch_embeddings,
        id_field="id"
    )

    # Then: Verify that the clean buffers are accurately forwarded to RedisVL loader
    mock_redis_vl_search_index.load.assert_called_once()

    # Extract and validate the exact kwargs dispatched to RedisVL
    dispatched_kwargs = mock_redis_vl_search_index.load.call_args.kwargs
    assert dispatched_kwargs["id_field"] == "id"
    assert dispatched_kwargs["preprocess"] is None

    # Verify the inner structure of the transmitted data buffer
    transmitted_data = dispatched_kwargs["data"]
    assert len(transmitted_data) == 1

    # Ensure our normalization constraints were implicitly triggered during the batch loop
    normalized_record = transmitted_data[0]
    assert normalized_record["id"] == "doc_unique_id"
    assert normalized_record["categories"] == "cyber,threat"  # List has been flattened
    assert isinstance(normalized_record["text_embedding"], bytes)  # Vector has been packed to float32 bytes

def test_ingestion_cache_health_delegates_to_driver(ingestion_cache: IngestionCacheClient) -> None:
    """Verify health() delegates directly to the underlying driver."""
    with patch.object(ingestion_cache._driver, "health", return_value=True) as mock_health:
        assert ingestion_cache.health() is True
        mock_health.assert_called_once()

def test_ingestion_cache_close_delegates_to_driver(ingestion_cache: IngestionCacheClient) -> None:
    """Verify close() delegates connection pool shutdown directly to the underlying driver."""
    with patch.object(ingestion_cache._driver, "close") as mock_close:
        ingestion_cache.close()
        mock_close.assert_called_once()