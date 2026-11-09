from unittest.mock import patch, MagicMock
import pytest
from pytest import MonkeyPatch
from fastapi.testclient import TestClient

from src.embedding import EmbeddingManager
from src.common.cache import JsonCacheClient, VectorCacheClient
from src.common.constants import Settings
from src.main import app


@pytest.fixture(scope="function")
def mock_embedding_engine() -> MagicMock:
    """Isolated, type-safe MagicMock for the EmbeddingManager."""
    mock = MagicMock(spec=EmbeddingManager)
    return mock

@pytest.fixture(scope="function")
def mock_json_cache() -> MagicMock:
    """Isolated, type-safe MagicMock for the JsonCacheClient.
    Guarantees strict iso-interface typing with production code
    while running ultra-fast unit tests.
    """
    mock = MagicMock(spec=JsonCacheClient)
    mock.init_pool.return_value = None
    return mock

@pytest.fixture(scope="function")
def mock_vector_cache() -> MagicMock:
    """Isolated, type-safe MagicMock for the VectorCacheClient.
    Guarantees strict iso-interface typing with production code
    while running ultra-fast unit tests.
    """
    mock = MagicMock(spec=VectorCacheClient)
    mock.init_pool.return_value = None
    return mock

########## HTTP TEST CLIENT ##########
@pytest.fixture(scope="function")
def mock_client(
        mock_settings: Settings,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
        mock_embedding_engine: MagicMock,
        monkeypatch: MonkeyPatch):
    """Isolated Test Client for routes.

    This function seems complex because we want FastAPI lifespan to be executed when we are
    testing the API part.

    If you need to test cache injections, into a router or a service of "api" module, don't use objects from FastAPI
    context, directly use mock_json_cache or mock_vector_cache fixtures to avoid namespace problems.
    """
    # Force injection of mock environment variables to maintain production isolation
    for key, value in mock_settings.model_dump(mode="json").items():
        if value is not None:
            monkeypatch.setenv(key, str(value))

    # Shut all heavy processes during startup, everything is already tested in their own modules.
    with patch("src.main.load_env_vars", return_value=mock_settings), \
            patch("src.main.init_embedding_engine", return_value=mock_embedding_engine.engine), \
            patch("src.main.run_pipeline") as mock_pipeline, \
            patch("src.main.init_json_pool", return_value=mock_json_cache), \
            patch("src.main.init_vector_pool", return_value=mock_vector_cache):
        # Prevent heavy embedding engine initialization
        mock_pipeline.return_value = None

        with TestClient(app, follow_redirects=False) as c:
            c.app.state.settings = mock_settings
            c.app.state.embedding_engine = mock_embedding_engine
            c.app.state.json_cache = mock_json_cache
            c.app.state.vector_cache = mock_vector_cache
            yield c
