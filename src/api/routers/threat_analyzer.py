import logging

from fastapi import APIRouter, Request, status

from src.api.schemas import AnalysisQueuedResponse, LogIngressPayload
from src.api.services import AnalysisQueueService

logger = logging.getLogger(__name__)

threat_analyzer = APIRouter(prefix="/threat_analyzer", tags=["Threat Analysis"])


@threat_analyzer.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest security event datasets into the asynchronous forensic analysis queue",
    description="Validates inbound log payload, enforces backpressure limits, and queues the job for background AI correlation.",
)
async def ingest_and_process_log(
        request: Request, payload: LogIngressPayload
) -> AnalysisQueuedResponse:
    """
    Validates HTTP boundaries and delegates asynchronous job persistence and FIFO queuing
    to AnalysisQueueService.
    """
    settings = request.state.settings
    json_cache = request.state.json_cache
    queue_cache = request.state.queue_cache

    logger.info(
        f"[THREAT ROUTER] Received ingress log request for platform: '{payload.platform}'"
    )
    queue_service = AnalysisQueueService(
        json_engine=json_cache,
        queue_engine=queue_cache,
        max_pending_size=settings.REDIS_QUEUE_MAX_PENDING_SIZE,
        job_ttl=settings.REDIS_JOBS_TTL,
    )
    return queue_service.submit_log(payload=payload)
