import logging

from fastapi import HTTPException, status

from src.api.schemas import AvailablePlatforms
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import IVectorSearchEngine
from src.soc_agent.schemas import ThreatAnalysis
from src.workflow import SocAgentWorkflow

logger = logging.getLogger(__name__)


class ForensicService:
    """
    Application Service acting as a bridge between FastAPI and the AI Domain.
    Handles infrastructure logging, telemetry, and error translation.
    """

    def __init__(
            self,
            llm_engine: ILlmEngine,
            embedding_engine: IEmbeddingEngine,
            vector_engine: IVectorSearchEngine,
    ):
        self._llm_engine = llm_engine
        self._embedding_engine = embedding_engine
        self._vector_engine = vector_engine

    async def analyze_and_report(
            self, platform: AvailablePlatforms, raw_log: str
    ) -> ThreatAnalysis:
        """
        Triggers the core AI workflow and translates domain outcomes
        or crashes into valid HTTP infrastructure exceptions.
        """
        logger.info(
            f"[FORENSIC SERVICE] Initiating forensic analysis pipeline for '{platform}'"
        )
        try:
            workflow = SocAgentWorkflow(
                llm_engine=self._llm_engine,
                embedding_engine=self._embedding_engine,
                vector_engine=self._vector_engine,
            )
            return await workflow.execute(platform=platform, raw_log=raw_log)
        except Exception as e:
            logger.error(f"[FORENSIC SERVICE] AI Workflow collapsed: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
