import logging
from unittest.mock import patch, mock_open, MagicMock

import pytest

from src.data_pipeline.pipelines.stix_pipeline import StixPipeline

# ============================================================================
# TEST BATCH CHUNKING
# ============================================================================
@patch("src.data_pipeline.pipelines.stix_pipeline.StixFilter")
@patch("src.data_pipeline.pipelines.stix_pipeline.StixExtractor")
@patch("src.data_pipeline.pipelines.stix_pipeline.StixCompiler")
def test_stix_pipeline_stream_chunking_boundaries_and_tail_flush(
        mock_compiler_cls, mock_extractor_cls, mock_filter_cls,
        mock_file_context, mock_infra, stix_mock_stream
):
    """
    GIVEN a STIX stream of 5 objects and a configuration of batch_size=2
    WHEN running the StixPipeline with all object filters forced to valid states
    THEN verify the orchestrator code executes exactly 3 sequential database operations:
         - Batch #1 (Inner conditional loop): 2 items
         - Batch #2 (Inner conditional loop): 2 items
         - Batch #3 (Tail buffer flush branch): 1 remaining item
    """
    # Arrange
    # Force fake StixFilter to return always True.
    mock_filter_instance = MagicMock()
    mock_filter_instance.is_valid_technique.return_value = True
    mock_filter_cls.return_value = mock_filter_instance

    # Force fake StixExtractor to return a minimalistic valid dict.
    mock_extractor_instance = MagicMock()
    mock_extractor_instance.extract_fields.side_effect = [
        {"id": "T1001", "mitre_id": "T1001", "semantic_hash": "h1"},
        {"id": "T1002", "mitre_id": "T1002", "semantic_hash": "h2"},
        {"id": "T1003", "mitre_id": "T1003", "semantic_hash": "h3"},
        {"id": "T1004", "mitre_id": "T1004", "semantic_hash": "h4"},
        {"id": "T1005", "mitre_id": "T1005", "semantic_hash": "h5"},
    ]
    mock_extractor_cls.return_value = mock_extractor_instance

    # Force fake StixCompiler to return a minimalistic valid compiled dict.
    mock_compiler_instance = MagicMock()
    mock_compiler_instance.compile_fields.side_effect = [
        {"id": "T1001", "mitre_id": "T1001", "semantic_hash": "h1", "compiled_text": "Txt 1"},
        {"id": "T1002", "mitre_id": "T1002", "semantic_hash": "h2", "compiled_text": "Txt 2"},
        {"id": "T1003", "mitre_id": "T1003", "semantic_hash": "h3", "compiled_text": "Txt 3"},
        {"id": "T1004", "mitre_id": "T1004", "semantic_hash": "h4", "compiled_text": "Txt 4"},
        {"id": "T1005", "mitre_id": "T1005", "semantic_hash": "h5", "compiled_text": "Txt 5"},
    ]
    mock_compiler_cls.return_value = mock_compiler_instance

    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context,
        batch_size=2
    )

    # Act
    with patch("builtins.open", mock_open()):
        pipeline.run()

    # Assert
    # Verify that the infrastructure components were triggered exactly 3 times (2 inner loops + 1 flush)
    assert mock_infra["embedding"].embed_documents.call_count == 3
    assert mock_infra["redis"].execute_bulk_upsert.call_count == 3
    assert mock_infra["redis"].set_remote_hashes.call_count == 3

    # Audit the structural sequence of chunking allocations via indexed call tuples
    upsert_calls = mock_infra["redis"].execute_bulk_upsert.call_args_list

    # Batch #1: First inner loop condition hit (Contains T1001 & T1002)
    payload_batch_1 = upsert_calls[0][1]["payload"]
    assert len(payload_batch_1) == 2
    assert payload_batch_1[0]["id"] == "T1001"

    # Batch #2: Second inner loop condition hit (Contains T1003 & T1004)
    payload_batch_2 = upsert_calls[1][1]["payload"]
    assert len(payload_batch_2) == 2
    assert payload_batch_2[0]["id"] == "T1003"

    # Batch #3: Tail flush boundary execution triggered after loop termination (Contains T1005)
    payload_batch_3 = upsert_calls[2][1]["payload"]
    assert len(payload_batch_3) == 1
    assert payload_batch_3[0]["id"] == "T1005"


# ============================================================================
# TEST NOMINAL CONDITIONS
# ============================================================================
def test_stix_pipeline_nominal_ingestion_flow(mock_file_context, mock_infra, stix_mock_stream):
    """
    GIVEN a valid STIX bundle file with 5 objects (2 valid techniques, 3 invalid/legacy items)
    WHEN running the StixPipeline under a clean nominal infrastructure state
    THEN verify it correctly filters and extracts data, and executes 1 bulk database upsert RTT.
    """
    # ---------------------------------------------------------
    # 1. ARRANGE
    # ---------------------------------------------------------
    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context,
        batch_size=50
    )
    # ---------------------------------------------------------
    # 2. ACT
    # ---------------------------------------------------------
    with patch("builtins.open", mock_open()):
        pipeline.run()
    # ---------------------------------------------------------
    # 3. ASSERT
    # ---------------------------------------------------------
    # Step A: Filesystem boundary validation
    mock_file_context.exists.assert_called_once()

    # Step B: Cache signatures initialization check, equal to [Step 1] into the pipeline.
    mock_infra["redis"].fetch_remote_hashes.assert_called_once()

    # Step C: Embedding vectorization verification, equal to [Step 3] into the pipeline.
    mock_infra["embedding"].embed_documents.assert_called_once()
    called_args, _ = mock_infra["embedding"].embed_documents.call_args
    embedded_texts = called_args[0]

    assert len(embedded_texts) == 2
    assert any("Technique ID: T1055" in text for text in embedded_texts)
    assert any("Technique ID: T1055.001" in text for text in embedded_texts)

    # Step D: Bulk database transactional upsert verification, equal to [Step 4] into the pipeline.
    mock_infra["redis"].execute_bulk_upsert.assert_called_once()
    _, upsert_kwargs = mock_infra["redis"].execute_bulk_upsert.call_args
    assert upsert_kwargs["id_field"] == "id"

    inserted_payload = upsert_kwargs["payload"]
    assert len(inserted_payload) == 2
    assert inserted_payload[0]["id"] == "T1055"
    assert inserted_payload[1]["id"] == "T1055.001"

    # Step E: Local-to-remote signatures synchronization check (1 RTT), equal to [Step 5] into the pipeline.
    mock_infra["redis"].set_remote_hashes.assert_called_once()
    set_hashes_args, _ = mock_infra["redis"].set_remote_hashes.call_args
    mutated_hashes = set_hashes_args[0]

    assert len(mutated_hashes) == 2
    assert "T1055" in mutated_hashes
    assert "T1055.001" in mutated_hashes


@patch("src.data_pipeline.pipelines.stix_pipeline.StixFilter")
@patch("src.data_pipeline.pipelines.stix_pipeline.StixExtractor")
def test_stix_pipeline_obeys_delta_cache_eviction_and_increments_counters(
        mock_extractor_cls, mock_filter_cls, mock_file_context, mock_infra, stix_mock_stream
):
    """
    GIVEN a STIX stream of objects where the delta-persistence dictates NO update is needed (_need_upsert returns False)
    WHEN running the StixPipeline
    THEN verify the orchestrator properly interprets the negative persistence decision,
         skips processing loops via the continue directive, and invokes no database writes or embeddings.
    """
    # Arrange
    # Force the structural filter to accept the items to reach the update decision branch
    mock_filter_instance = MagicMock()
    mock_filter_instance.is_valid_technique.return_value = True
    mock_filter_cls.return_value = mock_filter_instance

    mock_extractor_instance = MagicMock()
    mock_extractor_instance.extract_fields.return_value = {"id": "T1000", "mitre_id": "T1000", "semantic_hash": "h1"}
    mock_extractor_cls.return_value = mock_extractor_instance

    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context,
        batch_size=50
    )

    # CRITICAL: Mock the private method behavior directly on the instance we are testing.
    # We force it to return False (i.e. 'Object is already up to date, skip it')
    pipeline._need_upsert = MagicMock(return_value=False)

    # Act
    with patch("builtins.open", mock_open()):
        pipeline.run()

    # Assert
    # 1. Verify the orchestrator actually interrogated the _need_upsert rule
    assert pipeline._need_upsert.call_count > 0

    # 2. Verify that the negative decision completely blocked vectorization and persistence execution
    # (If 'not' or 'continue' were broken, these components would have been invoked)
    mock_infra["embedding"].embed_documents.assert_not_called()
    mock_infra["redis"].execute_bulk_upsert.assert_not_called()
    mock_infra["redis"].set_remote_hashes.assert_not_called()


# ============================================================================
# TEST PRIVATE FILTERING AND EXTRACTION
# ============================================================================
@patch("src.data_pipeline.pipelines.stix_pipeline.StixFilter")
@patch("src.data_pipeline.pipelines.stix_pipeline.StixExtractor")
def test_filter_extract_stix_object_nominal_flow(
        mock_extractor_cls, mock_filter_cls, mock_file_context, mock_infra
):
    """
    GIVEN a raw valid STIX object dictionary
    WHEN executing the private extraction helper _filter_extract_stix_object
    THEN verify it coordinates StixFilter and StixExtractor to return the expected dictionary layout.
    """
    # Arrange
    raw_object = {"type": "attack-pattern", "id": "attack-pattern--1"}
    expected_extracted = {"mitre_id": "T1000", "semantic_hash": "abc"}

    # Configure the mock instances returned by the class calls
    mock_filter_cls.return_value.is_valid_technique.return_value = True
    mock_extractor_cls.return_value.extract_fields.return_value = expected_extracted

    pipeline = StixPipeline(mock_infra["redis"], mock_infra["embedding"], mock_file_context)

    # Act
    result = pipeline._filter_extract_stix_object(stix_object=raw_object)
    # Assert
    assert result == expected_extracted
    mock_filter_cls.assert_called_once_with(stix_object=raw_object)
    mock_extractor_cls.assert_called_once_with(stix_object=raw_object)



@patch("src.data_pipeline.pipelines.stix_pipeline.StixFilter")
@patch("src.data_pipeline.pipelines.stix_pipeline.StixExtractor")
@pytest.mark.parametrize(
    "filter_valid, extractor_side_effect, expected_log_msg",
    [
        # Case 1: Rejected early by the StixFilter layer -> returns None, no log entry
        (False, None, None),
        # Case 2: Filter passes, but Extractor raises ValueError -> returns None, debug log captured via caplog
        (True, ValueError("Missing context schema keys"),
         "Evicting malformed STIX object because: Missing context schema keys")
    ]
)
def test_filter_extract_stix_object_eviction_scenarios(
        mock_extractor_cls, mock_filter_cls, mock_file_context, mock_infra, caplog,
        filter_valid, extractor_side_effect, expected_log_msg
):
    """
    GIVEN various faulty STIX object boundary scenarios (filter rejection or extractor validation failures)
    WHEN executing the private extraction helper _filter_extract_stix_object
    THEN verify it gracefully traps the failures, populates caplog at DEBUG level if necessary, and returns None.
    """
    # Arrange
    raw_object = {"type": "attack-pattern", "id": "attack-pattern--faulty"}
    pipeline = StixPipeline(mock_infra["redis"], mock_infra["embedding"], mock_file_context)

    mock_filter_cls.return_value.is_valid_technique.return_value = filter_valid

    if extractor_side_effect:
        mock_extractor_cls.return_value.extract_fields.side_effect = extractor_side_effect
    else:
        mock_extractor_cls.return_value.extract_fields.return_value = {}

    # Act
    with caplog.at_level(logging.DEBUG):
        result = pipeline._filter_extract_stix_object(stix_object=raw_object)
    # Assert
    assert result is None

    if expected_log_msg:
        assert len(caplog.records) == 1
        assert expected_log_msg in caplog.text
    else:
        assert len(caplog.records) == 0

# ============================================================================
# TEST PRIVATE SEMANTIC HASH COLLISION
# ============================================================================
@pytest.mark.parametrize(
    "remote_hashes, extracted_data, expected_result",
    [
        # Case 1: Mitre ID completely missing from remote index -> Upsert required (True)
        (
                {"T1055": "current_signature_hash"},
                {"mitre_id": "T1003", "semantic_hash": "some_hash_signature"},
                True
        ),
        # Case 2: Mitre ID exists, but hash signature mutated -> Upsert required (True)
        (
                {"T1055": "old_signature_hash"},
                {"mitre_id": "T1055", "semantic_hash": "new_signature_hash"},
                True
        ),
        # Case 3: Mitre ID exists and signature matches perfectly -> Eviction trigger (False)
        (
                {"T1055": "exact_matching_signature_hash"},
                {"mitre_id": "T1055", "semantic_hash": "exact_matching_signature_hash"},
                False
        )
    ]
)
def test_need_upsert_delta_cache_decision_matrix(
        mock_file_context, mock_infra, remote_hashes, extracted_data, expected_result
):
    """
    GIVEN various remote persistence state mappings and an extracted STIX payload signature
    WHEN evaluating structural update requirements via the private _need_upsert helper
    THEN verify it correctly resolves whether an integration database upsert is needed.
    """
    # Arrange
    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context
    )

    # Pre-populate the orchestrator delta state persistence registry
    pipeline._remote_hashes = remote_hashes
    # Act
    result = pipeline._need_upsert(extracted_data=extracted_data)
    # Assert
    assert result is expected_result

# ============================================================================
# TEST PIPELINE ERRORS
# ============================================================================
def test_stix_pipeline_aborts_early_when_file_not_found(mock_file_context, mock_infra, caplog):
    """
    GIVEN a missing target STIX bundle file path
    WHEN running the StixPipeline
    THEN verify it logs the specific failure at ERROR level via caplog and aborts execution early.
    """
    # Arrange: Force the file context mock to declare the file is missing on disk
    mock_file_context.exists.return_value = False

    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context
    )

    # Act
    with caplog.at_level(logging.ERROR):
        with pytest.raises(FileNotFoundError) as exc_info:
            pipeline.run()

    # Assert
    # 1. Verify the exception payload message matches
    assert "Target STIX file not found at: " in str(exc_info.value)

    # 2. Verify the exact failure message was intercepted in the outer try/except block
    assert len(caplog.records) == 1
    assert "Pipeline failed because: Target STIX file not found at: " in caplog.text

    # 3. Hard boundary check: No network or memory initialization should be triggered
    mock_infra["redis"].fetch_remote_hashes.assert_not_called()


def test_stix_pipeline_isolates_and_logs_critical_batch_ingestion_failures(
    mock_file_context, mock_infra, stix_mock_stream, caplog
):
    """
    GIVEN an operational pipeline that hits a critical database crash during a bulk upsert
    WHEN running the StixPipeline
    THEN verify the inner isolation guardrail captures the event, logs the exact post-mortem
         batch range metadata context at ERROR level, and propagates the exception.
    """
    # Arrange: Simulate a database dropout or cluster exception on bulk execution
    mock_infra["redis"].execute_bulk_upsert.side_effect = RuntimeError("Redis connection timeout lost")

    pipeline = StixPipeline(
        cache_client=mock_infra["redis"],
        embedding_engine=mock_infra["embedding"],
        file_path=mock_file_context,
        batch_size=50
    )

    # Act & Assert
    with caplog.at_level(logging.ERROR):
        # The pipeline must re-raise the batch error to prevent silent data loss corruption
        with patch("builtins.open", mock_open()), pytest.raises(RuntimeError) as exc_info:
            pipeline.run()

    assert "Redis connection timeout lost" in str(exc_info.value)
    # Audit the post-mortem telemetry in caplog records
    expected_critical_log = (
        "CRITICAL: Ingestion failure encountered on Batch #1. "
        "Range: T1055 to T1055.001. Reason: Redis connection timeout lost"
    )
    assert any(expected_critical_log in record.message for record in caplog.records)
