import os
from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from src.common.constants import Settings
from src.common.cache import IngestionCacheClient, JsonCacheClient, VectorCacheClient
from src.data_pipeline import StixPipeline
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.embedding import EmbeddingManager
from src.startup import load_env_vars, init_embedding_engine, run_pipeline, init_json_pool, init_vector_pool


# =========================================================================
# load_env_vars
# =========================================================================
def test_load_env_vars_success(mock_settings):
    """Test load_env_vars success on FastAPI lifespan"""
    # Extract Settings
    complete_env_payload = mock_settings.model_dump(mode="json")
    stringified_env = {k: str(v) for k, v in complete_env_payload.items()}

    # patch os.environ to load env vars as if it was really injected at runtime
    with patch.dict(os.environ, stringified_env, clear=True):
        settings = load_env_vars()

    # check all env vars are present and not None
    for field_name in Settings.model_fields.keys():
        assert hasattr(settings, field_name)
        assert getattr(settings, field_name) is not None

def test_load_env_vars_crash(caplog):
    """Test load_env_vars crash because missing env variables"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValidationError):
            load_env_vars()
        assert "Environment variables loading failed because: " in caplog.text

# =========================================================================
# init_embedding_engine
# =========================================================================
def test_init_embedding_engine_success(mock_settings):
    """Test standard initialization of the embedding engine (nominal path)."""
    mock_factory = MagicMock(spec=EmbeddingManager)
    # init_embedding to return None preventing heavy loading
    mock_factory.engine._init_embedding.return_value = None
    mock_factory.engine.engine_name = "mock-huggingface"

    with patch("src.startup.embedding.EmbeddingManager", return_value=mock_factory) as mock_manager_class:
        engine = init_embedding_engine(settings=mock_settings)
        # check EmbeddingManager is called
        mock_manager_class.assert_called_once_with(
            provider=mock_settings.EMBEDDING_ENGINE,
            model_name=mock_settings.EMBEDDING_MODEL_NAME
        )
        assert engine == mock_factory.engine
        assert engine.engine_name == "mock-huggingface"


def test_init_embedding_engine_crash(mock_settings, caplog):
    """Test that an initialization failure logs the exact reason and raises the exception."""
    with patch("src.startup.embedding.EmbeddingManager", side_effect=RuntimeError("CUDA out of memory")):
        with pytest.raises(RuntimeError):
            init_embedding_engine(settings=mock_settings)

        assert "Embedding engine initialization failed because: " in caplog.text


# =========================================================================
# run_pipeline
# =========================================================================
def test_run_pipeline_success(mock_settings):
    """Test nominal path where pipeline runs and gracefully closes connection pool."""
    mock_engine = MagicMock(spec=IEmbeddingEngine)
    mock_ingestion_client = MagicMock(spec=IngestionCacheClient)
    mock_pipeline_instance = MagicMock(spec=StixPipeline)

    with patch("src.startup.pipeline.IngestionCacheClient", return_value=mock_ingestion_client) as mock_client_class, \
            patch("src.startup.pipeline.StixPipeline", return_value=mock_pipeline_instance) as mock_pipeline_class:
        run_pipeline(settings=mock_settings, embedding_engine=mock_engine)

        # check infrastructure instance
        mock_client_class.assert_called_once_with(
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=True,
            db=mock_settings.REDIS_VECTOR_POOL_DB_ID,
            target_vector_field=mock_settings.REDIS_VL_VECTOR_FIELD,
            semantic_hashes_key=mock_settings.MITRE_SEMANTIC_HASHES_KEY,
        )

        # check low-level plumbing
        mock_ingestion_client.init_pool.assert_called_once()
        mock_ingestion_client.init_search_index.assert_called_once_with(
            schema_path=mock_settings.MITRE_INDEX_SCHEMA_PATH)

        # check pipeline instance
        mock_pipeline_class.assert_called_once_with(
            cache_client=mock_ingestion_client,
            embedding_engine=mock_engine,
            file_path=mock_settings.MITRE_JSON_PATH,
            batch_size=50
        )
        mock_pipeline_instance.run.assert_called_once()

        # check connexions are released
        mock_ingestion_client.close.assert_called_once()

def test_run_pipeline_crash(mock_settings, caplog):
    """Test that any pipeline exception is caught, logged, cleanly re-raised, and connection pool is still closed."""
    mock_engine = MagicMock(spec=IEmbeddingEngine)
    mock_ingestion_client = MagicMock(spec=IngestionCacheClient)

    # Simulate crash during connexions pool creation
    mock_ingestion_client.init_pool.side_effect = ConnectionError("Redis cluster unreachable")

    with patch("src.startup.pipeline.IngestionCacheClient", return_value=mock_ingestion_client), \
         patch("src.startup.pipeline.StixPipeline"):
        with pytest.raises(ConnectionError) as exc_info:
            run_pipeline(settings=mock_settings, embedding_engine=mock_engine)

        # check expection is re-raised
        assert str(exc_info.value) == "Redis cluster unreachable"
        # check logs
        assert "Ingestion pipeline failed because: " in caplog.text
        assert "Redis cluster unreachable" in caplog.text

        # check connexions are released even after a crash
        mock_ingestion_client.close.assert_called_once()


# =========================================================================
# init_json_pool
# =========================================================================
def test_init_json_pool_success(mock_settings):
    """Test nominal creation and pool initialization of the JSON cache client."""
    mock_json_cache = MagicMock(spec=JsonCacheClient)
    mock_json_cache.init_pool.return_value = None

    with patch("src.startup.cache_client.JsonCacheClient", return_value=mock_json_cache) as mock_client_class:
        client = init_json_pool(settings=mock_settings)

        # check infrastructure instance
        mock_client_class.assert_called_once_with(
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_JSON_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=True,
            db=mock_settings.REDIS_JSON_POOL_DB_ID
        )
        # check connexions pool is started and ready to accept connexions
        mock_json_cache.init_pool.assert_called_once()
        assert client == mock_json_cache


def test_init_json_pool_crash(mock_settings, caplog):
    """Test that JSON cache client failure logs infrastructure metadata and re-raises."""
    with patch("src.startup.cache_client.JsonCacheClient", side_effect=ConnectionRefusedError("Redis port blocked")):
        with pytest.raises(ConnectionRefusedError):
            init_json_pool(settings=mock_settings)

        # check logs clearly indicate what happened
        assert "Creating cache client specialized in JSON documents" in caplog.text
        assert f"on {mock_settings.REDIS_HOST}:{mock_settings.REDIS_PORT}" in caplog.text
        assert f"db: {mock_settings.REDIS_JSON_POOL_DB_ID}" in caplog.text
        assert "failed because: Redis port blocked" in caplog.text


# =========================================================================
# init_vector_pool
# =========================================================================
def test_init_vector_pool_success(mock_settings):
    """Test nominal creation, initialization and catalog sync of the Vector cache client."""
    mock_vector_cache = MagicMock(spec=VectorCacheClient)
    mock_vector_cache.init_pool.return_value = None
    mock_embedding_engine = MagicMock(spec=IEmbeddingEngine)

    with patch("src.startup.cache_client.VectorCacheClient", return_value=mock_vector_cache) as mock_client_class:
        client = init_vector_pool(settings=mock_settings, embedding_engine=mock_embedding_engine)

        # check infrastructure instance
        mock_client_class.assert_called_once_with(
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=False,
            db=mock_settings.REDIS_VECTOR_POOL_DB_ID,
            embedding_engine=mock_embedding_engine,
            index_path=mock_settings.MITRE_INDEX_SCHEMA_PATH,
        )

        # check low-level plumbing
        mock_vector_cache.init_pool.assert_called_once()
        mock_vector_cache.sync_lifespan_catalog.assert_called_once()
        assert client == mock_vector_cache


def test_init_vector_pool_crash(mock_settings, caplog):
    """Test that Vector cache client failure logs infrastructure metadata and re-raises."""
    mock_engine = MagicMock(spec=IEmbeddingEngine)

    with patch("src.startup.cache_client.VectorCacheClient", side_effect=RuntimeError("Index layout mismatch")):
        with pytest.raises(RuntimeError):
            init_vector_pool(settings=mock_settings, embedding_engine=mock_engine)

        assert "Creating cache client specialized in VECTOR documents" in caplog.text
        assert f"on {mock_settings.REDIS_HOST}:{mock_settings.REDIS_PORT}" in caplog.text
        assert f"db: {mock_settings.REDIS_VECTOR_POOL_DB_ID}" in caplog.text
        assert "failed because: Index layout mismatch" in caplog.text