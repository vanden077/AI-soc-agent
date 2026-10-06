from typing import Any
import pytest
from fastapi.testclient import TestClient

from src.common.cache import RedisClient, RedisVectorClient


def test_health_check(mock_client: TestClient):
    """Test health check route for API"""
    response = mock_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}

@pytest.mark.parametrize(
    "json_ok, vector_ok, expected_status, expected_json",
    [
        # both caches are OK
        (True,
         True,
         200,
         {"status": "ok", "JSON_POOL": True, "VECTOR_POOL": True}
         ),
        # json_cache is KO
        (False,
         True,
         503,
         {"status": "ko", "JSON_POOL": False, "VECTOR_POOL": True}
         ),
        # vector_cache is KO
        (True,
         False,
         503,
         {"status": "ko", "JSON_POOL": True, "VECTOR_POOL": False}
         ),
        # both caches are KO
        (False,
         False,
         503,
         {"status": "ko", "JSON_POOL": False, "VECTOR_POOL": False}),
    ]
)
def test_cache_health_check(
        mocker,
        mock_client: TestClient,
        json_ok: bool,
        vector_ok: bool,
        expected_status: int,
        expected_json: dict[str, Any]
):
    """Test health check route for cache connexions pools"""
    if not json_ok:
        mocker.patch.object(RedisClient, "health", return_value=False)

    if not vector_ok:
        mocker.patch.object(RedisVectorClient, "health", return_value=False)

    response = mock_client.get("/health/cache")
    assert response.status_code == expected_status
    assert response.json() == expected_json