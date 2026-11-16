from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.main import app
from src.persistence.interfaces import IJsonStorageEngine, IVectorSearchEngine


@pytest.fixture(scope="function")
def mock_embedding_engine(mocker) -> MagicMock:
    """Isolated interface-bound mock for IEmbeddingEngine."""
    return mocker.MagicMock(spec=IEmbeddingEngine)


@pytest.fixture(scope="function")
def mock_llm_engine(mocker) -> MagicMock:
    """Isolated interface-bound mock for ILlmEngine."""
    return mocker.MagicMock(spec=ILlmEngine)


@pytest.fixture(scope="function")
def mock_json_cache(mocker) -> MagicMock:
    """Isolated interface-bound mock for IJsonStorageEngine."""
    return mocker.MagicMock(spec=IJsonStorageEngine)


@pytest.fixture(scope="function")
def mock_vector_cache(mocker) -> MagicMock:
    """Isolated interface-bound mock for IVectorSearchEngine."""
    return mocker.MagicMock(spec=IVectorSearchEngine)


@pytest.fixture(scope="function")
def mock_client(
    mocker,
    mock_settings: Settings,
    mock_json_cache: MagicMock,
    mock_vector_cache: MagicMock,
    mock_embedding_engine: MagicMock,
    mock_llm_engine: MagicMock,
) -> Generator[TestClient, None, None]:
    """
    Isolated HTTP TestClient executing FastAPI lifespan with mocked startup boundaries.
    """
    mocker.patch("src.main.load_env_vars", return_value=mock_settings)
    mocker.patch("src.main.init_embedding_engine", return_value=mock_embedding_engine)
    mocker.patch("src.main.run_pipeline")
    mocker.patch("src.main.init_json_pool", return_value=mock_json_cache)
    mocker.patch("src.main.init_vector_pool", return_value=mock_vector_cache)
    mocker.patch("src.main.init_llm", return_value=mock_llm_engine)

    with TestClient(app, follow_redirects=False) as client:
        yield client