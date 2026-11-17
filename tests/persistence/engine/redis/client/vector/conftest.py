import pytest


@pytest.fixture(scope="function")
def sample_query_vector() -> list[float]:
    """Provide a standard 384-dimensional normalized query vector for similarity search tests."""
    return [0.1] * 384
