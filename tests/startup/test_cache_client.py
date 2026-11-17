import logging
from unittest.mock import MagicMock

import pytest
from src.constants import Settings
from src.persistence.interfaces import (
    IJsonStorageEngine,
    IQueueEngine,
    IVectorSearchEngine,
)
from src.startup.cache_client import init_json_pool, init_queue_pool, init_vector_pool


def test_init_json_pool_nominal_creates_isolated_json_engine(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Nominal: instantiates PersistenceManager and delegates to create_json_engine with decode_responses=True."""
    with caplog.at_level(logging.INFO):
        mock_json_engine: MagicMock = mocker.MagicMock(spec=IJsonStorageEngine)
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_json_engine.return_value = mock_json_engine

        result = init_json_pool(settings=mock_settings)

        mock_manager_cls.assert_called_once_with(
            provider=mock_settings.PERSISTENCE_ENGINE
        )
        mock_manager_cls.return_value.create_json_engine.assert_called_once_with(
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_JSON_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=True,
            db=mock_settings.REDIS_JSON_POOL_DB_ID,
        )
        assert result is mock_json_engine
        assert "[JSON POOL STARTUP] Init pool..." in caplog.text


def test_init_json_pool_logs_and_reraises_on_exception(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Error: logs host, port, db, and root cause before re-raising exception."""
    with caplog.at_level(logging.ERROR):
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_json_engine.side_effect = ConnectionError(
            "Connection refused"
        )

        with pytest.raises(ConnectionError, match="Connection refused"):
            init_json_pool(settings=mock_settings)

        assert (
                "[JSON POOL STARTUP] Creating persistence client specialized in JSON documents, "
                f"on {mock_settings.REDIS_HOST}:{mock_settings.REDIS_PORT}, "
                f"db: {mock_settings.REDIS_JSON_POOL_DB_ID}, "
                "failed because: Connection refused" in caplog.text
        )


def test_init_vector_pool_nominal_creates_isolated_vector_search_engine(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Nominal: instantiates PersistenceManager and delegates to create_vector_search_engine with decode_responses=False."""
    with caplog.at_level(logging.INFO):
        mock_vector_engine: MagicMock = mocker.MagicMock(spec=IVectorSearchEngine)
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_vector_search_engine.return_value = (
            mock_vector_engine
        )

        result = init_vector_pool(settings=mock_settings)

        mock_manager_cls.assert_called_once_with(
            provider=mock_settings.PERSISTENCE_ENGINE
        )
        mock_manager_cls.return_value.create_vector_search_engine.assert_called_once_with(
            index_path=mock_settings.MITRE_INDEX_SCHEMA_PATH,
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=False,
            db=mock_settings.REDIS_VECTOR_POOL_DB_ID,
        )
        assert result is mock_vector_engine
        assert "[VECTOR POOL STARTUP] Init pool..." in caplog.text


def test_init_vector_pool_logs_and_reraises_on_exception(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Error: logs host, port, db, and root cause before re-raising exception."""
    with caplog.at_level(logging.ERROR):
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_vector_search_engine.side_effect = (
            RuntimeError("Missing index")
        )

        with pytest.raises(RuntimeError, match="Missing index"):
            init_vector_pool(settings=mock_settings)

        assert (
                "[VECTOR POOL STARTUP] Creating persistence client specialized in VECTOR documents, "
                f"on {mock_settings.REDIS_HOST}:{mock_settings.REDIS_PORT}, "
                f"db: {mock_settings.REDIS_VECTOR_POOL_DB_ID} "
                "failed because: Missing index" in caplog.text
        )


def test_init_queue_pool_nominal_creates_isolated_queue_engine(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Nominal: instantiates PersistenceManager and delegates to create_queue_engine with decode_responses=True."""
    with caplog.at_level(logging.INFO):
        mock_queue_engine: MagicMock = mocker.MagicMock(spec=IQueueEngine)
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_queue_engine.return_value = (
            mock_queue_engine
        )

        result = init_queue_pool(settings=mock_settings)

        mock_manager_cls.assert_called_once_with(
            provider=mock_settings.PERSISTENCE_ENGINE
        )
        mock_manager_cls.return_value.create_queue_engine.assert_called_once_with(
            pending_key=mock_settings.REDIS_QUEUE_PENDING_KEY,
            done_key=mock_settings.REDIS_QUEUE_DONE_KEY,
            max_done_history=mock_settings.REDIS_QUEUE_MAX_DONE_HISTORY,
            host=mock_settings.REDIS_HOST,
            port=mock_settings.REDIS_PORT,
            username=mock_settings.REDIS_USERNAME,
            password=mock_settings.REDIS_PASSWORD,
            max_size_pool=mock_settings.REDIS_JSON_POOL_SIZE,
            retry_strategy=mock_settings.REDIS_RETRY_STRATEGY,
            ssl=mock_settings.REDIS_SSL,
            decode_responses=True,
            db=mock_settings.REDIS_JSON_POOL_DB_ID,
        )
        assert result is mock_queue_engine
        assert "[QUEUE POOL STARTUP] Init pool..." in caplog.text


def test_init_queue_pool_logs_and_reraises_on_exception(
        mocker,
        mock_settings: Settings,
        caplog,
) -> None:
    """Error: logs host, port, db, and root cause before re-raising exception."""
    with caplog.at_level(logging.ERROR):
        mock_manager_cls = mocker.patch("src.startup.cache_client.PersistenceManager")
        mock_manager_cls.return_value.create_queue_engine.side_effect = ConnectionError(
            "Queue connection refused"
        )

        with pytest.raises(ConnectionError, match="Queue connection refused"):
            init_queue_pool(settings=mock_settings)

        assert (
                "[QUEUE POOL STARTUP] Creating persistence client specialized in job queuing, "
                f"on {mock_settings.REDIS_HOST}:{mock_settings.REDIS_PORT}, "
                f"db: {mock_settings.REDIS_JSON_POOL_DB_ID}, "
                "failed because: Queue connection refused" in caplog.text
        )
