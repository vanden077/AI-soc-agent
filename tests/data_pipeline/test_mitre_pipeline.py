from unittest.mock import MagicMock, patch

import pytest
import redis
from tests.dataset_test import STIX_MOCK
from langchain_core.documents import Document

from schemas import Settings
from src.data_pipeline.exceptions import MitreDownloadError
from src.data_pipeline.mitre_pipeline import MitrePipeline


def test_start_pipeline(mock_settings: Settings):
    """Normal process"""
    with (
        patch(
            "src.data_pipeline.mitre_pipeline.MitrePipeline._get_mitre_attack_stix_json"
        ) as mock_load,
        patch(
            "src.data_pipeline.mitre_pipeline.MitrePipeline._inject_data_into_redis"
        ) as mock_inject,
    ):
        mock_load.return_value = None
        mock_inject.return_value = None
        mitre_pipeline = MitrePipeline(mock_settings)
        mitre_pipeline._mitre_json = STIX_MOCK
        mitre_pipeline.start_pipeline()

        assert mock_load.called
        assert mock_inject.called


PIPELINE_EXCEPTIONS_DATA = [
    # HuggingFace Embeddings Failures
    (
        "src.data_pipeline.mitre_pipeline.HuggingFaceEmbeddings",
        OSError(
            "No internet connection to download 'all-MiniLM-L6-v2' and cache is missing."
        ),
        "HuggingFace Embeddings",
    ),
    (
        "src.data_pipeline.mitre_pipeline.HuggingFaceEmbeddings",
        ValueError("Model name 'all-MiniLM-L6-v2' is invalid or typo detected."),
        "HuggingFace Typo",
    ),
    # Redis Config / Validation Failures
    (
        "src.data_pipeline.mitre_pipeline.RedisConfig",
        ValueError("Unsupported distance metric format or missing arguments."),
        "RedisConfig Invalid Metric",
    ),
    # Redis Vector Store Connection & Database Engines Errors
    (
        "src.data_pipeline.mitre_pipeline.RedisVectorStore",
        redis.exceptions.ConnectionError(
            "Error 111 connecting to localhost:6379. Connection refused."
        ),
        "Redis Connection Refused",
    ),
    (
        "src.data_pipeline.mitre_pipeline.RedisVectorStore",
        redis.exceptions.ResponseError(
            "Index 'mitre_attack_v1' already exists with a conflicting schema configuration."
        ),
        "Redis Schema Conflict",
    ),
    (
        "src.data_pipeline.mitre_pipeline.RedisVectorStore",
        redis.exceptions.TimeoutError(
            "Timeout reaching Redis cluster nodes during bulk vector insertion."
        ),
        "Redis Bulk Timeout",
    ),
]


@pytest.mark.parametrize(
    "target_mock_path, simulated_exception, test_case_id", PIPELINE_EXCEPTIONS_DATA
)
def test_pipeline_crashing(
    target_mock_path: str, simulated_exception: Exception, test_case_id: str, mock_settings: Settings
):
    """Ensure that start_pipeline safely catches and wraps any infrastructure exceptions into a strict RuntimeError."""
    with (
        patch(
            "src.data_pipeline.mitre_pipeline.MitrePipeline._get_mitre_attack_stix_json"
        ) as mock_load,
        patch(
            "src.data_pipeline.mitre_pipeline.MitrePipeline._inject_data_into_redis",
            side_effect=simulated_exception,
        ),
    ):
        mock_load.return_value = None

        with patch(target_mock_path, side_effect=simulated_exception):
            mitre_pipeline = MitrePipeline(mock_settings)
            mitre_pipeline._mitre_json = STIX_MOCK

            with pytest.raises(RuntimeError) as err:
                mitre_pipeline.start_pipeline()
            assert str(simulated_exception) in str(err.value)


def test_get_mitre_attack_stix_json(mock_settings: Settings):
    """Normal process, get stix json"""
    with (
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.check_matrix_is_locally_cached"
        ) as mock_check,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.load_json_mitre_in_memory"
        ) as mock_load,
    ):
        mock_check.return_value = True
        mock_load.return_value = STIX_MOCK

        mitre_pipeline = MitrePipeline(mock_settings)
        mitre_pipeline._get_mitre_attack_stix_json()

        mock_check.assert_called_once()
        mock_load.assert_called_once()
        assert mitre_pipeline._mitre_json == STIX_MOCK


def test_local_mitre_repository_do_not_exists(mock_settings: Settings):
    """Get stix json, repository data.mitre.enterprise-attack.json do not exist"""
    with (
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.check_matrix_is_locally_cached"
        ) as mock_check,
        patch("src.data_pipeline.common.pipeline_utils.PipelineUtils.create_local_matrix") as mock_create,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.load_json_mitre_in_memory"
        ) as mock_load,
    ):
        mock_check.return_value = False
        mock_create.return_value = None
        mock_load.return_value = STIX_MOCK

        mitre_pipeline = MitrePipeline(mock_settings)
        mitre_pipeline._get_mitre_attack_stix_json()

        mock_check.assert_called_once()
        mock_create.assert_called_once()
        mock_load.assert_called_once()
        assert mitre_pipeline._mitre_json == STIX_MOCK


def test_get_mitre_cache_invalid_or_missing(mock_settings: Settings):
    """Get stix json, repository exists but is empty"""
    with (
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.check_matrix_is_locally_cached"
        ) as mock_check,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.load_json_mitre_in_memory"
        ) as mock_load,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.download_latest_mitre_version"
        ) as mock_download,
    ):
        mock_check.return_value = True
        mock_load.side_effect = [None, STIX_MOCK]
        mock_download.return_value = None

        mitre_pipeline = MitrePipeline(mock_settings)
        mitre_pipeline._get_mitre_attack_stix_json()

        mock_check.assert_called_once()
        assert mock_load.call_count == 2
        assert mitre_pipeline._mitre_json == STIX_MOCK


def test_get_mitre_raise_exception(mock_settings: Settings):
    """Get stix json fails even after retry"""
    with (
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.check_matrix_is_locally_cached"
        ) as mock_check,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.load_json_mitre_in_memory"
        ) as mock_load,
        patch(
            "src.data_pipeline.common.pipeline_utils.PipelineUtils.download_latest_mitre_version"
        ) as mock_download,
    ):
        mock_check.return_value = True
        mock_load.side_effect = [None, None]
        mock_download.return_value = None

        with pytest.raises(MitreDownloadError) as err:
            mitre_pipeline = MitrePipeline(mock_settings)
            mitre_pipeline._get_mitre_attack_stix_json()
        assert (
            str(err.value)
            == f"❌ MITRE JSON is not downloadable or invalid, process aborted. Please check: {mitre_pipeline._mitre_json_path}"
        )


def test_inject_data_into_redis_with_metadata_schema(mock_settings: Settings):
    """Verify that the pipeline configures TAG indices and enforces stable IDs for UPSERT capabilities."""
    with (
        patch(
            "src.data_pipeline.mitre_pipeline.HuggingFaceEmbeddings"
        ) as mock_embeddings_cls,
        patch(
            "src.data_pipeline.mitre_pipeline.RedisVectorStore"
        ) as mock_redis_store_cls,
    ):
        mock_embeddings_instance = MagicMock()
        mock_embeddings_cls.return_value = mock_embeddings_instance

        mitre_pipeline = MitrePipeline(mock_settings)
        mitre_pipeline._vector_docs = [
            Document(
                page_content="T1055: Process Injection description",
                metadata={
                    "attack_code": "T1055",
                    "technique_name": "Process Injection",
                    "platforms": ["windows", "linux"],
                    "tactics": ["defense-evasion", "privilege-escalation"],
                },
            )
        ]

        mitre_pipeline._inject_data_into_redis()

        # Historic assertions preserved
        mock_embeddings_cls.assert_called_once_with(model_name="all-MiniLM-L6-v2")
        mock_redis_store_cls.from_documents.assert_called_once()

        _, called_kwargs = mock_redis_store_cls.from_documents.call_args

        assert called_kwargs["documents"] == mitre_pipeline._vector_docs
        assert called_kwargs["embedding"] == mock_embeddings_instance

        # New deterministic IDs validation for UPSERT strategy
        assert "ids" in called_kwargs
        assert called_kwargs["ids"] == ["T1055"]

        # Comprehensive configuration checks
        config_obj = called_kwargs["config"]
        assert config_obj.index_name == mitre_pipeline._index_name
        assert config_obj.redis_url == mitre_pipeline._redis_url
        assert config_obj.distance_metric == "COSINE"
        assert config_obj.indexing_algorithm == "HNSW"

        # New strict metadata schema assertions
        assert hasattr(config_obj, "metadata_schema")
        assert config_obj.metadata_schema == [
            {"name": "platforms", "type": "tag"},
            {"name": "tactics", "type": "tag"},
        ]
