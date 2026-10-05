import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

health_route = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

@health_route.get("", summary="Check API is alive.")
async def health_check() -> JSONResponse:
    """Return the status of the service."""
    return JSONResponse(content={"status": "ok"}, status_code=200)

@health_route.get("/cache", summary="Check Redis connexions are alive.")
async def health_check(request: Request) -> JSONResponse:
    """Return the status the connexion pools to Redis server."""
    json_cache = request.state.json_cache
    vector_cache = request.state.vector_cache
    status_code = 503

    # ping Redis trough json pool
    json_cache_status = json_cache.health()
    # ping Redis through vector pool
    vector_cache_status = vector_cache.health()

    if json_cache_status and vector_cache_status:
        status_code = 200

    return JSONResponse(content={
        "status": "ok" if status_code == 200 else "ko",
        "JSON_POOL": json_cache_status,
        "VECTOR_POOL": vector_cache_status
    }, status_code=status_code)