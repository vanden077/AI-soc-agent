import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

health_route = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

@health_route.get("", summary="Check API is alive.")
async def health_check() -> JSONResponse:
    """Return the status of the service."""
    return JSONResponse(content="ok", status_code=200)