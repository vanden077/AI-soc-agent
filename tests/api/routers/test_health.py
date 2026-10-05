from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from common.cache import RedisClient, RedisVectorClient
from common.cache.driver.redis_driver import RedisDriver


def test_health_check(mock_client: TestClient):
    """Test health check route for API"""
    response = mock_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}

# TODO this test is fucked up because we should'nt do this in production (maintaining 2 pools on the same service).
#  It is a simple POC, so we do it anyway, solution => force cache client to implement health function instead of inherinting it from driver.
# @pytest.mark.parametrize(
#     "json_ok, vector_ok, expected_status, expected_json",
#     [
#         # both caches are OK
#         (True,
#          True,
#          200,
#          {"status": "ok", "JSON_POOL": True, "VECTOR_POOL": True}
#          ),
#         # json_cache is KO
#         (False,
#          True,
#          503,
#          {"status": "ko", "JSON_POOL": False, "VECTOR_POOL": True}
#          ),
#         # vector_cache is KO
#         (True,
#          False,
#          503,
#          {"status": "ko", "JSON_POOL": True, "VECTOR_POOL": False}
#          ),
#         # both caches are KO
#         (False,
#          False,
#          503,
#          {"status": "ko", "JSON_POOL": False, "VECTOR_POOL": False}),
#     ]
# )
# def test_cache_health_check(
#         mock_client: TestClient,
#         json_ok: bool,
#         vector_ok: bool,
#         expected_status: int,
#         expected_json: dict[str, Any]
# ):
#     """Test health check route for cache connexions pools"""
#     if not json_ok:
#         #patch_json = patch.object(mock_client.app.state.json_cache, "health", return_value=False)
#         mock_client.app.state.json_cache._client.ping = MagicMock(
#             side_effect=Exception("Redis JSON down")
#         )
#
#     if not vector_ok:
#         #patch.object(mock_client.app.state.vector_cache, "health", return_value=False)
#         mock_client.app.state.vector_cache._client.ping = MagicMock(
#             side_effect=Exception("Redis Vector down")
#         )
#
#     response = mock_client.get("/health/cache")
#     assert response.status_code == expected_status
#     assert response.json() == expected_json