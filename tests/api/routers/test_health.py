from typing import Any
import pytest
from fastapi.testclient import TestClient

@pytest.mark.parametrize(
    "json_status, vector_status, expected_status, expected_json",
    [
        # both caches are ok
        (True,
         True,
         200,
         {"status": "ok"}
         ),
        # json_cache is KO
        (False,
         True,
         503,
         {"status": "ko"}
         ),
        # vector_cache is KO
        (True,
         False,
         503,
         {"status": "ko"}
         ),
        # everything is KO
        (False,
         False,
         503,
         {"status": "ko"}),
    ]
)
def test_health_check(
        mock_json_cache,
        mock_vector_cache,
        mock_client: TestClient,
        json_status: bool,
        vector_status: bool,
        expected_status: int,
        expected_json: dict[str, Any]
):
    """Test health check route for cache connexions pools"""
    mock_json_cache.health.return_value = json_status
    mock_vector_cache.health.return_value = vector_status

    response = mock_client.get("/health")
    assert response.status_code == expected_status
    assert response.json() == expected_json