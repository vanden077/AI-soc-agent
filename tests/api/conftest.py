"""
================================================================================
ARCHITECTURAL NOTE: Modular Test Framework & Microservices Readiness
================================================================================

DESIGN PHILOSOPHY & CONTEXT:
In a standalone Proof of Concept (PoC) or a basic FastAPI application, the setup
implemented below—featuring dynamic router cleanup, lazy-evaluated custom markers,
and scoped fixture mutation—would undoubtedly be considered OVER-ENGINEERING.
A simple global configuration or sequential environment patching would suffice.

THE "MODULAR MONOLITH" DEMONSTRATION:
However, this project is purposefully built as a "Modular Monolith". In the real
world, the vast majority of software projects grow into tightly coupled monophonic
monoliths, requiring near-total rewrites when the business scales and demands a
transition to microservices.

The explicit goal here is to demonstrate how to architect a codebase that avoids
this trap from day one. By strictly isolating both production code and test
infrastructure within highly cohesive, loosely coupled domain boundaries (e.g.,
this 'api' module), we ensure that the entire domain remains 100% portable.

HOW IT WORKS:
1. Complete Encapsulation: The custom pytest hooks (`pytest_configure`) and
   the semantic sugar decorators (`@dev_mode`, `@prod_mode`) are declared and
   contained strictly within this local `conftest.py`. If this directory is ever
   extracted into a separate microservice repository, its entire testing suite
   migrates seamlessly without leaving dead configuration or technical debt in
   a global root configuration file (like a top-level `pyproject.toml`).

2. Lazy Evaluation Pattern: Decorators are encapsulated inside functions to
   defer evaluation to test runtime. This bypasses Python's import-time execution
   warnings (`PytestUnknownMarkWarning`) while preserving a pristine, self-contained
   module scope.

3. Global State Anti-Pollution: FastAPI caches imported router states. To prevent
   cross-test state leak (e.g., dynamic dev routes persisting into prod runs),
   this fixture takes a snapshot of `app.router.routes` *before* the application
   lifespan triggers, and rigorously restores it in a `finally` block. This
   guarantees absolute test isolation under parallel test execution.

By prioritizing Developer Experience (DX) and strict module isolation, this architecture
proves that a monolith can be elegant, robust, and transition-ready.
================================================================================
"""


from unittest.mock import patch
import pytest
from pytest import FixtureRequest, MonkeyPatch
from langchain_huggingface import HuggingFaceEmbeddings
from fastapi.testclient import TestClient

from src.common.cache import RedisClient, RedisVectorClient
from src.embedding import EmbeddingManager
from src.common.constants import Settings
from src.main import app

# ==============================================================================
# PYTEST CONFIGURATION HOOKS
# ==============================================================================
def pytest_configure(config):
    """Register custom markers to prevent pytest from raising unrecognized marker warnings."""
    config.addinivalue_line(
        "markers",
        "env_override(env_name): Dynamically patches the Settings.ENV property before FastAPI lifespan triggers."
    )

# ==============================================================================
# DECORATORS (DX HELPERS)
# ==============================================================================
# We define these aliases to provide a clean, declarative API for test functions.
# This avoids leaking verbose pytest mark syntax into individual test files.
def dev_mode(func):
    """Default environment is "TESTS".
    If you need a test in a development environment, just use the decorator @dev_mode."""
    return pytest.mark.env_override("development")(func)

def prod_mode(func):
    """Default environment is "TESTS".
        If you need a test in a production environment, just use the decorator @prod_mode."""
    return pytest.mark.env_override("production")(func)


########## HTTP TEST CLIENT ##########
@pytest.fixture(scope="function")
def mock_client(
        mock_settings: Settings,
        json_cache: RedisClient,
        mock_embedding_engine: EmbeddingManager,
        vector_cache: RedisVectorClient,
        monkeypatch: MonkeyPatch,
        request: FixtureRequest):
    """Isolated Test Client for routes.

    This function seems complex because we want FastApi lifespan to be executed when we are
    testing the API part.

    If you need to test cache injections, into a router or a service of "api" module, don't use objects from fastapi
    context, directly use json_cache or vector_cache fixtures to avoid namespace problems.

    Introspects the calling test metadata to look for custom environment overrides
    (@dev_mode / @prod_mode) and mutates the configuration context before the
    FastAPI lifespan runs.
    """
    # Look for the decorator metadata on the test function
    marker = request.node.get_closest_marker("env_override")
    target_env = marker.args[0] if marker and marker.args else None

    # Mutate the frozen Settings instance if an environment override is requested
    effective_settings = (
        mock_settings.model_copy(update={"ENV": target_env})
        if target_env else mock_settings
    )

    # inject fake env vars to stay iso-prod
    for key, value in effective_settings.model_dump(mode="json").items():
        if value is not None:
            monkeypatch.setenv(key, str(value))

    # because this fixture is dynamically updatable, we need to keep in memory initial routes state in order to
    # restore it between each test.
    initial_routes = list(app.router.routes)

    # replace Redis Client instances by fixture using FakeRedis
    with patch("src.common.cache.RedisClient", return_value=json_cache):
        with patch("src.common.cache.RedisVectorClient", return_value=vector_cache):
            # CRITICAL FIX: Patch the heavy LangChain constructor *BEFORE* entering the TestClient.
            # This ensures that when FastAPI triggers the real production 'lifespan' function,
            # it builds a lightweight "empty shell" instead of loading full PyTorch/Torch weights.
            with patch.object(HuggingFaceEmbeddings, "__init__", return_value=None):
                with TestClient(app, follow_redirects=False) as c:
                    # inject settings instance into FastApi context
                    c.app.state.settings = mock_settings
                    # inject Redis instances into FastApi context
                    c.app.state.json_cache = json_cache
                    c.app.state.embedding_engine = mock_embedding_engine
                    c.app.state.vector_cache = vector_cache

                    try:
                        yield c
                    finally:
                        # restore all routes to their initial state.
                        # once test is done, clean all routes dynamically added by using decorators @dev_mode
                        # or @ prod_mode. This way, next test will be executed on a clean app.
                        app.router.routes = initial_routes
