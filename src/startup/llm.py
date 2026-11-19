import asyncio
import logging

from src.api.schemas import AvailablePlatforms
from src.api.services import ForensicService
from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.llm import LlmManager
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import IVectorSearchEngine

logger = logging.getLogger(__name__)


def init_llm(settings: Settings) -> ILlmEngine:
    """Start LLM"""
    try:
        logger.info(
            f"[LLM STARTUP] Load LLM {settings.LLM_ENGINE}, model {settings.LLM_MODEL}..."
        )
        llm = LlmManager(
            base_url=settings.LLM_URL,
            llm_engine=settings.LLM_ENGINE,
            llm_model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
        )
        return llm.engine
    except Exception as e:
        logger.error(f"[LLM STARTUP] LLM initialization failed because: {e!s}")
        raise


def warmup_llm_background(
        llm_engine: ILlmEngine,
        embedding_engine: IEmbeddingEngine,
        vector_engine: IVectorSearchEngine,
) -> asyncio.Task[None]:
    """Schedule a non-blocking background warmup probe through ForensicService without persisting anything."""

    async def _run_warmup() -> None:
        try:
            logger.info("[LLM WARMUP] Warming up AI forensic pipeline in background...")
            forensic_service = ForensicService(
                llm_engine=llm_engine,
                embedding_engine=embedding_engine,
                vector_engine=vector_engine,
            )
            await asyncio.to_thread(
                asyncio.run,
                forensic_service.analyze_and_report(
                    platform=AvailablePlatforms.LINUX,
                    raw_log="sshd[1]: Accepted publickey for root from 127.0.0.1 port 22 ssh2",
                ),
            )
            logger.info("[LLM WARMUP] AI forensic pipeline is warm and ready.")
        except Exception as err:
            logger.warning(f"[LLM WARMUP] Background warmup probe failed: {err!s}")

    return asyncio.create_task(_run_warmup())
