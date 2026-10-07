########## EMBEDDING ENGINE ##########
from unittest.mock import patch
import pytest
from langchain_huggingface import HuggingFaceEmbeddings
from fastapi.testclient import TestClient

from src.common.cache import RedisClient, RedisVectorClient
from src.embedding import EmbeddingManager
from src.common.constants import Settings
from src.main import app

########## HTTP TEST CLIENT ##########
@pytest.fixture(scope="function")
def mock_client(
        mock_settings: Settings,
        json_cache: RedisClient,
        mock_embedding_engine: EmbeddingManager,
        vector_cache: RedisVectorClient,
        monkeypatch):
    """Isolated Test Client for routes.
    This function seems complex because we want FastApi lifespan to be executed when we are
    testing the API part.

    If you need to test cache injections, into a router or a service of "api" module, don't use objects from fastapi
    context, directly use json_cache or vector_cache fixtures to avoid namespace problems.
    """
    # inject fake env vars to stay iso-prod
    for key, value in mock_settings.model_dump(mode="json").items():
        if value is not None:
            monkeypatch.setenv(key, str(value))

    # replace Redis Client instances by fixture using FakeRedis
    with patch("src.common.cache.RedisClient", return_value=json_cache):
        with patch("src.common.cache.RedisVectorClient", return_value=vector_cache):
            # CRITICAL FIX: Patch the heavy LangChain constructor *BEFORE* entering the TestClient.
            # This ensures that when FastAPI triggers the real production 'lifespan' function,
            # it builds a lightweight "empty shell" instead of loading full PyTorch/Torch weights.
            with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None):
                with TestClient(app) as c:
                    # inject settings instance into FastApi context
                    c.app.state.settings = mock_settings
                    # inject redis instances into FastApi context
                    c.app.state.json_cache = json_cache
                    c.app.state.embedding_engine = mock_embedding_engine
                    c.app.state.vector_cache = vector_cache
                    yield c