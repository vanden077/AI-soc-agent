import logging
from typing import Annotated

from fastapi import APIRouter, Request, status, Body

from src.api.dev_setup import THREAT_ANALYZER_EXAMPLES
from src.api.schemas import AnalysisQueuedResponse, LogIngressPayload
from src.api.services import AnalysisQueueService, JobProgressService

logger = logging.getLogger(__name__)

threat_analyzer = APIRouter(prefix="/threat_analyzer", tags=["Threat Analysis"])


@threat_analyzer.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest security event datasets into the asynchronous forensic analysis queue",
    description="Validates inbound log payload, enforces backpressure limits, and queues the job for background AI correlation.",
)
async def ingest_and_process_log(
        request: Request, payload: Annotated[LogIngressPayload, Body(openapi_examples=THREAT_ANALYZER_EXAMPLES)],
) -> AnalysisQueuedResponse:
    """
    Validates HTTP boundaries and delegates asynchronous job persistence and FIFO queuing
    to AnalysisQueueService, then broadcasts updated queue progress.
    """
    settings = request.state.settings
    json_cache = request.state.json_cache
    queue_cache = request.state.queue_cache
    progress_service: JobProgressService = request.state.progress_service

    logger.info(
        f"[THREAT ROUTER] Received ingress log request for platform: '{payload.platform}'"
    )
    queue_service = AnalysisQueueService(
        json_engine=json_cache,
        queue_engine=queue_cache,
        max_pending_size=settings.REDIS_QUEUE_MAX_PENDING_SIZE,
        job_ttl=settings.REDIS_JOBS_TTL,
        job_key_prefix=settings.REDIS_JSON_DOCUMENT_KEY,
    )
    queued_response = queue_service.submit_log(payload=payload)
    await progress_service.notify_progress()
    return queued_response
