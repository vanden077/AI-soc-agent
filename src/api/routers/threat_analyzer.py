import logging

from fastapi import APIRouter, Request, status

from src.api.schemas import LogIngressPayload
from src.api.services import ForensicService
from src.soc_agent.schemas import ThreatAnalysis

logger = logging.getLogger(__name__)

threat_analyzer = APIRouter(prefix="/threat_analyzer", tags=["Threat Analysis"])


@threat_analyzer.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Ingest security event datasets and execute full forensic AI workflow",
    description="Important note: first request can be long because of LLM warm up phase.",
)
async def ingest_and_process_log(
    request: Request, payload: LogIngressPayload
) -> ThreatAnalysis:
    """
    Validates HTTP boundaries and delegates the entire triage/KNN/LLM-Response
    chain to an isolated, ephemeral runtime service instance.
    """
    llm_engine = request.state.llm_engine
    embedding_engine = request.state.embedding_engine
    vector_cache = request.state.vector_cache

    logger.info(
        f"[THREAT ROUTER] Received ingress log request for platform: '{payload.platform}'"
    )
    forensic_service = ForensicService(
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_cache,
    )
    return await forensic_service.analyze_and_report(
        platform=payload.platform, raw_log=payload.raw_log
    )
