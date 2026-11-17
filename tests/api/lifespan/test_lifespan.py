from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from src.constants import Settings
from src.main import lifespan


async def test_lifespan_executes_all_helpers_and_closes_resources_on_stop(
        mocker,
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
        mock_llm_engine: MagicMock,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
) -> None:
    """Nominal: executes startup sequence, yields context, and closes pools on shutdown."""
    prod_settings = mock_settings.model_copy(update={"ENV": "production"})
    mock_load_env = mocker.patch("src.main.load_env_vars", return_value=prod_settings)
    mock_dev_helpers = mocker.patch("src.main.configure_dev_helpers")
    mock_init_embed = mocker.patch(
        "src.main.init_embedding_engine", return_value=mock_embedding_engine
    )
    mock_download_stix = mocker.patch("src.main.download_stix_file")
    mock_run_pipe = mocker.patch("src.main.run_pipeline")
    mock_init_json = mocker.patch(
        "src.main.init_json_pool", return_value=mock_json_cache
    )
    mock_init_vec = mocker.patch(
        "src.main.init_vector_pool", return_value=mock_vector_cache
    )
    mock_init_llm = mocker.patch("src.main.init_llm", return_value=mock_llm_engine)

    test_app = FastAPI()

    async with lifespan(test_app) as context:
        mock_load_env.assert_called_once()
        mock_dev_helpers.assert_not_called()
        mock_init_embed.assert_called_once_with(settings=prod_settings)
        mock_download_stix.assert_called_once_with(settings=prod_settings)
        mock_run_pipe.assert_called_once_with(
            settings=prod_settings, embedding_engine=mock_embedding_engine
        )
        mock_init_json.assert_called_once_with(settings=prod_settings)
        mock_init_vec.assert_called_once_with(settings=prod_settings)
        mock_init_llm.assert_called_once_with(settings=prod_settings)

        assert context["settings"] is prod_settings
        assert context["embedding_engine"] is mock_embedding_engine
        assert context["llm_engine"] is mock_llm_engine
        assert context["json_cache"] is mock_json_cache
        assert context["vector_cache"] is mock_vector_cache

        mock_json_cache.close.assert_not_called()
        mock_vector_cache.close.assert_not_called()

    mock_json_cache.close.assert_called_once()
    mock_vector_cache.close.assert_called_once()


async def test_lifespan_configures_dev_helpers_in_development_mode(
        mocker,
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
        mock_llm_engine: MagicMock,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
) -> None:
    """Branch ENV == 'development': registers dev redirect helpers on the FastAPI app."""
    dev_settings = mock_settings.model_copy(update={"ENV": "development"})
    mocker.patch("src.main.load_env_vars", return_value=dev_settings)
    mock_dev_helpers = mocker.patch("src.main.configure_dev_helpers")
    mocker.patch("src.main.init_embedding_engine", return_value=mock_embedding_engine)
    mocker.patch("src.main.download_stix_file")
    mocker.patch("src.main.run_pipeline")
    mocker.patch("src.main.init_json_pool", return_value=mock_json_cache)
    mocker.patch("src.main.init_vector_pool", return_value=mock_vector_cache)
    mocker.patch("src.main.init_llm", return_value=mock_llm_engine)

    test_app = FastAPI()

    async with lifespan(test_app):
        mock_dev_helpers.assert_called_once_with(test_app)


async def test_lifespan_gracefully_releases_acquired_resources_on_mid_flight_crash(
        mocker,
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
        mock_json_cache: MagicMock,
) -> None:
    """Cleanup: closes json_cache if init_vector_pool crashes mid-flight."""
    prod_settings = mock_settings.model_copy(update={"ENV": "production"})
    mocker.patch("src.main.load_env_vars", return_value=prod_settings)
    mocker.patch("src.main.init_embedding_engine", return_value=mock_embedding_engine)
    mocker.patch("src.main.download_stix_file")
    mocker.patch("src.main.run_pipeline")
    mocker.patch("src.main.init_json_pool", return_value=mock_json_cache)
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
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
) -> None:
    """Branch json_cache is None: safely exits finally block without calling close()."""
    prod_settings = mock_settings.model_copy(update={"ENV": "production"})
    mocker.patch("src.main.load_env_vars", return_value=prod_settings)
    mocker.patch("src.main.init_embedding_engine", return_value=mock_embedding_engine)
    mocker.patch("src.main.download_stix_file")
    mocker.patch("src.main.run_pipeline")
    mocker.patch("src.main.init_json_pool", side_effect=RuntimeError("JSON pool crash"))

    test_app = FastAPI()

    with pytest.raises(RuntimeError, match="JSON pool crash"):
        async with lifespan(test_app):
            pytest.fail("Lifespan should not yield when init_json_pool fails")
