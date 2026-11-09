from fastapi.testclient import TestClient


def test_redirect_to_docs_when_env_is_development(mock_client: TestClient):
    """Ensures that the root URL redirects to /docs when running in dev mode."""
    response = mock_client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
