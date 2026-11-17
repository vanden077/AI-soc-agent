import logging
from unittest.mock import MagicMock

import pytest
from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.persistence.interfaces import IVectorIngestionEngine
from src.startup.pipeline import run_pipeline


def test_run_pipeline_nominal_executes_stix_pipeline_and_closes_engine(
    mocker,
    mock_settings: Settings,
    caplog,
) -> None:
    """Nominal: initializes ephemeral ingestion engine, runs StixPipeline, and closes engine in finally."""
    with caplog.at_level(logging.INFO):
        mock_embedding_engine: MagicMock = mocker.MagicMock(spec=IEmbeddingEngine)
        mock_ingestion_engine: MagicMock = mocker.MagicMock(spec=IVectorIngestionEngine)

        mock_manager_cls = mocker.patch("src.startup.pipeline.PersistenceManager")
        mock_manager_cls.return_value.create_vector_ingestion_engine.return_value = (
            mock_ingestion_engine
        )
        mock_pipeline_cls = mocker.patch("src.startup.pipeline.StixPipeline")

        run_pipeline(settings=mock_settings, embedding_engine=mock_embedding_engine)

        mock_manager_cls.assert_called_once_with(
            provider=mock_settings.PERSISTENCE_ENGINE
        )
        mock_manager_cls.return_value.create_vector_ingestion_engine.assert_called_once_with(
            index_path=mock_settings.MITRE_INDEX_SCHEMA_PATH,
            target_vector_field=mock_settings.REDIS_VL_VECTOR_FIELD,
            semantic_hashes_key=mock_settings.MITRE_SEMANTIC_HASHES_KEY,
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=True,
            db=mock_settings.REDIS_VECTOR_POOL_DB_ID,
        )
        mock_pipeline_cls.assert_called_once_with(
            cache_client=mock_ingestion_engine,
            embedding_engine=mock_embedding_engine,
            file_path=mock_settings.MITRE_JSON_PATH,
            batch_size=50,
        )
        mock_pipeline_cls.return_value.run.assert_called_once()
        mock_ingestion_engine.close.assert_called_once()
        assert (
            "[PIPELINE STARTUP] Terminated, data are vectorized and ready."
            in caplog.text
        )


def test_run_pipeline_skips_close_when_engine_creation_fails(
    mocker,
    mock_settings: Settings,
    caplog,
) -> None:
    """Error before engine instantiation: logs error, re-raises, and skips close() safely."""
    with caplog.at_level(logging.ERROR):
        mock_embedding_engine: MagicMock = mocker.MagicMock(spec=IEmbeddingEngine)
        mock_manager_cls = mocker.patch("src.startup.pipeline.PersistenceManager")
        mock_manager_cls.return_value.create_vector_ingestion_engine.side_effect = (
            RuntimeError("Index schema invalid")
        )

        with pytest.raises(RuntimeError, match="Index schema invalid"):
            run_pipeline(settings=mock_settings, embedding_engine=mock_embedding_engine)

        assert (
            "[PIPELINE STARTUP] Pipeline failed because: Index schema invalid"
            in caplog.text
        )


def test_run_pipeline_closes_engine_even_when_pipeline_execution_fails(
    mocker,
    mock_settings: Settings,
    caplog,
) -> None:
    """Error during pipeline run: logs error, re-raises, and still closes ingestion engine in finally."""
    with caplog.at_level(logging.ERROR):
        mock_embedding_engine: MagicMock = mocker.MagicMock(spec=IEmbeddingEngine)
        mock_ingestion_engine: MagicMock = mocker.MagicMock(spec=IVectorIngestionEngine)

        mock_manager_cls = mocker.patch("src.startup.pipeline.PersistenceManager")
        mock_manager_cls.return_value.create_vector_ingestion_engine.return_value = (
            mock_ingestion_engine
        )
        mock_pipeline_cls = mocker.patch("src.startup.pipeline.StixPipeline")
        mock_pipeline_cls.return_value.run.side_effect = OSError(
            "STIX JSON file not found"
        )

        with pytest.raises(OSError, match="STIX JSON file not found"):
            run_pipeline(settings=mock_settings, embedding_engine=mock_embedding_engine)

        mock_ingestion_engine.close.assert_called_once()
        assert (
            "[PIPELINE STARTUP] Pipeline failed because: STIX JSON file not found"
            in caplog.text
        )
