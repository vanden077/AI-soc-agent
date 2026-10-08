from ..conftest import dev_mode, prod_mode
from fastapi.testclient import TestClient


@dev_mode
def test_redirect_to_docs_when_env_is_development(mock_client: TestClient):
    """Ensures that the root URL redirects to /docs when running in dev mode."""
    response = mock_client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"

@prod_mode
def test_no_redirect_when_env_is_production(mock_client: TestClient):
    """Ensures that the root URL returns a 404 in production environment."""
    response = mock_client.get("/")
    assert response.status_code == 404