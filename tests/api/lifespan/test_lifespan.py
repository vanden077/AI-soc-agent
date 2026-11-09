import pytest
from unittest.mock import MagicMock, patch


async def test_lifespan_executes_all_helpers_and_closes_resources_on_stop(mock_settings):
    """Test all helpers are called on application startup during the lifespan."""
    mock_embedding_engine = MagicMock()
    mock_json_cache = MagicMock()
    mock_vector_cache = MagicMock()

    with patch(f"src.main.load_env_vars", return_value=mock_settings) as mock_load_env, \
            patch(f"src.main.init_embedding_engine", return_value=mock_embedding_engine) as mock_init_embed, \
            patch(f"src.main.run_pipeline") as mock_run_pipe, \
            patch(f"src.main.init_json_pool", return_value=mock_json_cache) as mock_init_json, \
            patch(f"src.main.init_vector_pool", return_value=mock_vector_cache) as mock_init_vec:
        from src.main import app, lifespan

        async with lifespan(app) as context:
            # Check boot sequence.
            mock_load_env.assert_called_once()
            mock_init_embed.assert_called_once_with(settings=mock_settings)
            mock_run_pipe.assert_called_once_with(settings=mock_settings, embedding_engine=mock_embedding_engine)
            mock_init_json.assert_called_once_with(settings=mock_settings)
            mock_init_vec.assert_called_once_with(settings=mock_settings, embedding_engine=mock_embedding_engine)

            # Check FastAPI context
            assert context["settings"] == mock_settings
            assert context["embedding_engine"] == mock_embedding_engine
            assert context["json_cache"] == mock_json_cache
            assert context["vector_cache"] == mock_vector_cache

            # At this step connexions pool should not be closed.
            mock_json_cache.close.assert_not_called()
            mock_vector_cache.close.assert_not_called()

        # When stopping app, connexions pool should be gracefully released.
        mock_json_cache.close.assert_called_once()
        mock_vector_cache.close.assert_called_once()


async def test_lifespan_gracefully_releases_acquired_resources_on_mid_flight_crash(mock_settings):
    """If the last pool created in lifespan crashes (vector pool),
    check that first pool (json pool) is gracefully released to prevent Redis socket leaks."""
    mock_embedding_engine = MagicMock()
    mock_json_cache = MagicMock()

    with patch(f"src.main.load_env_vars", return_value=mock_settings) as mock_load_env, \
            patch(f"src.main.init_embedding_engine", return_value=mock_embedding_engine) as mock_init_embed, \
            patch(f"src.main.run_pipeline") as mock_run_pipe, \
            patch(f"src.main.init_json_pool", return_value=mock_json_cache) as mock_init_json, \
            patch(f"src.main.init_vector_pool", side_effect=Exception("Any kind of exception")):
        from src.main import app, lifespan

        with pytest.raises(Exception):
            async with lifespan(app):
                assert False # <= it should not be called

        mock_json_cache.close.assert_called_once()