import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

health_route = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

@health_route.get("", summary="Check api and persistence are alive.")
async def health_check(request: Request) -> JSONResponse:
    """If all components are OK return 200 else 503."""
    json_cache = request.state.json_cache
    vector_cache = request.state.vector_cache
    status_code = 503

    if json_cache.health() and vector_cache.health():
        status_code = 200

    return JSONResponse(content={
        "status": "ok" if status_code == 200 else "ko",
    }, status_code=status_code)