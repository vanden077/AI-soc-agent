from uuid import UUID

from fastapi import APIRouter, Request, status

from src.api.schemas import AnalysisJobRecord, AnalysisQueuedResponse
from src.api.services import JobQueryService

threat_jobs = APIRouter(prefix="/threat_analyzer", tags=["Threat Analysis"])


def _build_query_service(request: Request) -> JobQueryService:
    """Instantiate read-only JobQueryService from request application state."""
    return JobQueryService(
        json_engine=request.state.json_cache,
        queue_engine=request.state.queue_cache,
        job_key_prefix=request.state.settings.REDIS_JSON_DOCUMENT_KEY
    )


@threat_jobs.get(
    "/pending",
    status_code=status.HTTP_200_OK,
    summary="List pending forensic analysis jobs",
    description="Returns all queued jobs waiting in the FIFO queue in processing order.",
)
async def list_pending_jobs(request: Request) -> list[AnalysisQueuedResponse]:
    """Delegate pending queue listing to JobQueryService."""
    return _build_query_service(request).get_pending_jobs()


@threat_jobs.get(
    "/done",
    status_code=status.HTTP_200_OK,
    summary="List completed forensic analysis job reports",
    description="Returns bounded history of processed forensic analysis records (most recent first).",
)
async def list_done_jobs(request: Request) -> list[AnalysisJobRecord]:
    """Delegate completed jobs listing to JobQueryService."""
    return _build_query_service(request).get_done_jobs()


@threat_jobs.get(
    "/job/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve status and report of a specific forensic analysis job",
    description="Returns the persisted job metadata, current execution state, and final MITRE ATT&CK analysis report if completed.",
)
async def get_job_status(request: Request, job_id: UUID) -> AnalysisJobRecord:
    """Validate UUID path parameter and fetch job details via JobQueryService."""
    return _build_query_service(request).get_job(job_id=str(job_id))
