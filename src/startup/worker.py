import asyncio
import logging

from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import (
    IJsonStorageEngine,
    IQueueEngine,
    IVectorSearchEngine,
)
from src.worker import AnalysisWorker

logger = logging.getLogger(__name__)


def start_analysis_worker(
        settings: Settings,
        json_engine: IJsonStorageEngine,
        queue_engine: IQueueEngine,
        llm_engine: ILlmEngine,
        embedding_engine: IEmbeddingEngine,
        vector_engine: IVectorSearchEngine,
) -> asyncio.Task[None]:
    """Instantiate and schedule the background forensic analysis worker task."""
    logger.info("[WORKER STARTUP] Scheduling background forensic worker...")
    worker = AnalysisWorker(
        json_engine=json_engine,
        queue_engine=queue_engine,
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_engine,
        job_ttl=settings.REDIS_JOBS_TTL,
        poll_interval=settings.WORKER_POLL_INTERVAL,
    )
    return asyncio.create_task(worker.run())
