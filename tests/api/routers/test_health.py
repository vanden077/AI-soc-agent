from typing import Any
import pytest
from fastapi.testclient import TestClient
from src.common.cache import RedisClient, RedisVectorClient

@pytest.mark.parametrize(
    "json_ok, vector_ok, expected_status, expected_json",
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

    response = mock_client.get("/health")
    assert response.status_code == expected_status
    assert response.json() == expected_json