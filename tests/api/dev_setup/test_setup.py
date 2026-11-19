from fastapi import status
from fastapi.testclient import TestClient


def test_redirect_to_docs_when_env_is_development(mock_client: TestClient) -> None:
    """Ensures that the root URL redirects to /docs when running in dev mode."""
    response = mock_client.get("/")
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "/docs"


def test_custom_swagger_ui_injects_progress_badge(mock_client: TestClient) -> None:
    """Ensures that /docs serves Swagger UI HTML with the live WebSocket progress badge script."""
    response = mock_client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
    assert "soc-progress-badge" in response.text
    assert "/threat_analyzer/progress" in response.text
