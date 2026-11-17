from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from src.constants import Settings
from src.main import lifespan


async def test_lifespan_executes_all_helpers_and_closes_resources_on_stop(
        lifespan_mocks: SimpleNamespace,
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
        mock_llm_engine: MagicMock,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
        mock_queue_cache: MagicMock,

) -> None:
    """Nominal: executes startup sequence, yields context, and closes pools on shutdown."""
    prod_settings = mock_settings.model_copy(update={"ENV": "production"})
    lifespan_mocks.load_env_vars.return_value = prod_settings

    test_app = FastAPI()

    async with lifespan(test_app) as context:
        lifespan_mocks.load_env_vars.assert_called_once()
        lifespan_mocks.configure_dev_helpers.assert_not_called()
        lifespan_mocks.init_embedding_engine.assert_called_once_with(settings=prod_settings)
        lifespan_mocks.download_stix_file.assert_called_once_with(settings=prod_settings)
        lifespan_mocks.run_pipeline.assert_called_once_with(settings=prod_settings,
                                                            embedding_engine=mock_embedding_engine)
        lifespan_mocks.init_json_pool.assert_called_once_with(settings=prod_settings)
        lifespan_mocks.init_vector_pool.assert_called_once_with(settings=prod_settings)
        lifespan_mocks.init_queue_pool.assert_called_once_with(settings=prod_settings)
        lifespan_mocks.init_llm.assert_called_once_with(settings=prod_settings)

        assert context["settings"] is prod_settings
        assert context["embedding_engine"] is mock_embedding_engine
        assert context["llm_engine"] is mock_llm_engine
        assert context["json_cache"] is mock_json_cache
        assert context["vector_cache"] is mock_vector_cache
        assert context["queue_cache"] is mock_queue_cache

        mock_json_cache.close.assert_not_called()
        mock_vector_cache.close.assert_not_called()
        mock_queue_cache.close.assert_not_called()

    mock_json_cache.close.assert_called_once()
    mock_vector_cache.close.assert_called_once()
    mock_queue_cache.close.assert_called_once()


async def test_lifespan_configures_dev_helpers_in_development_mode(
        lifespan_mocks: SimpleNamespace,
) -> None:
    """Branch ENV == 'development': registers dev redirect helpers on the FastAPI app."""
    test_app = FastAPI()

    async with lifespan(test_app):
        lifespan_mocks.configure_dev_helpers.assert_called_once_with(test_app)


async def test_lifespan_gracefully_releases_acquired_resources_on_mid_flight_crash(
        mocker,
        lifespan_mocks: SimpleNamespace,
        mock_json_cache: MagicMock,
) -> None:
    """Cleanup: closes json_cache if init_vector_pool crashes mid-flight."""
    mocker.patch(
        "src.main.init_vector_pool", side_effect=RuntimeError("Vector pool crash")
    )
    test_app = FastAPI()

    with pytest.raises(RuntimeError, match="Vector pool crash"):
        async with lifespan(test_app):
            pytest.fail("Lifespan should not yield when init_vector_pool fails")

    mock_json_cache.close.assert_called_once()


async def test_lifespan_skips_close_when_first_pool_fails(
        mocker,
        lifespan_mocks: SimpleNamespace,
) -> None:
    """Branch json_cache is None: safely exits finally block without calling close()."""
    mocker.patch("src.main.init_json_pool", side_effect=RuntimeError("JSON pool crash"))
    test_app = FastAPI()

    with pytest.raises(RuntimeError, match="JSON pool crash"):
        async with lifespan(test_app):
            pytest.fail("Lifespan should not yield when init_json_pool fails")


async def test_lifespan_gracefully_releases_json_and_vector_on_queue_pool_crash(
        mocker,
        lifespan_mocks: SimpleNamespace,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
) -> None:
    """Cleanup: closes json_cache and vector_cache if init_queue_pool crashes mid-flight."""
    mocker.patch(
        "src.main.init_queue_pool", side_effect=RuntimeError("Queue pool crash")
    )
    test_app = FastAPI()

    with pytest.raises(RuntimeError, match="Queue pool crash"):
        async with lifespan(test_app):
            pytest.fail("Lifespan should not yield when init_queue_pool fails")

    mock_json_cache.close.assert_called_once()
    mock_vector_cache.close.assert_called_once()
