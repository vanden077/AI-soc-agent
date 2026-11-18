import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.dev_setup import configure_dev_helpers
from src.api.routers import health_route, threat_analyzer, threat_jobs
from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import (
    IJsonStorageEngine,
    IQueueEngine,
    IVectorSearchEngine,
)
from src.startup import (
    download_stix_file,
    init_embedding_engine,
    init_json_pool,
    init_llm,
    init_queue_pool,
    init_vector_pool,
    load_env_vars,
    run_pipeline,
    start_analysis_worker,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s:  %(message)s")

noisy_loggers = [
    "langchain",
    "langchain_core",
    "langchain_community",
    "ollama",
    "httpx",
    "httpcore",
    "redisvl",
]

for logger_name in noisy_loggers:
    target_logger = logging.getLogger(logger_name)
    target_logger.setLevel(logging.WARNING)
    target_logger.propagate = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(ai_soc_agent: FastAPI):
    """
    If anything crash here, service can't be healthy, we just let it crash for deeper investigation.
    """
    # ==============================================================================
    # PHASE 1: Load, validate and freeze env vars.
    # ==============================================================================
    settings: Settings = load_env_vars()

    # redirection from / to /docs
    if settings.ENV == "development":
        configure_dev_helpers(ai_soc_agent)

    # ==============================================================================
    # PHASE 2: Check JSON stix mitre is locally present, if not, download it
    # ==============================================================================
    download_stix_file(settings=settings)

    # ==============================================================================
    # PHASE 3: Initialize embedding engine, and push its instance into context
    # ==============================================================================
    embedding_engine: IEmbeddingEngine = init_embedding_engine(settings=settings)

    # ==============================================================================
    # PHASE 4: Check mitre_attack_v1 vector database integrity
    # ==============================================================================
    run_pipeline(settings=settings, embedding_engine=embedding_engine)

    json_cache = None
    vector_cache = None
    queue_cache = None
    worker_task = None

    try:
        # ==============================================================================
        # PHASE 5: Prepare connexions pools for runtime, and push instances into context
        # ==============================================================================
        json_cache: IJsonStorageEngine = init_json_pool(settings=settings)
        vector_cache: IVectorSearchEngine = init_vector_pool(settings=settings)
        queue_cache: IQueueEngine = init_queue_pool(settings=settings)

        # ==============================================================================
        # PHASE 6: Initialize LLM engine, and push its instance into context
        # ==============================================================================
        llm_engine: ILlmEngine = init_llm(settings=settings)

        # ==============================================================================
        # PHASE 7: Start background forensic analysis worker
        # ==============================================================================
        worker_task: asyncio.Task[None] = start_analysis_worker(
            settings=settings,
            json_engine=json_cache,
            queue_engine=queue_cache,
            llm_engine=llm_engine,
            embedding_engine=embedding_engine,
            vector_engine=vector_cache,
        )

        logger.info("🚀 STARTUP COMPLETE")

        # injections into FastAPI context
        yield {
            "settings": settings,
            "embedding_engine": embedding_engine,
            "llm_engine": llm_engine,
            "json_cache": json_cache,
            "vector_cache": vector_cache,
            "queue_cache": queue_cache,
        }
    finally:
        # Gracefully stop background task
        if worker_task is not None:
            worker_task.cancel()
            await asyncio.gather(worker_task, return_exceptions=True)
        # Gracefully release json persistence connexions pool
        if json_cache is not None:
            json_cache.close()
        # Gracefully release vector persistence connexions pool
        if vector_cache is not None:
            vector_cache.close()
        # Gracefully release queue connexions pool
        if queue_cache is not None:
            queue_cache.close()

    logger.info("👋 Gracefully closed app... Bye")


app = FastAPI(title="AI Soc agent.", lifespan=lifespan)
app.include_router(health_route)
app.include_router(threat_analyzer)
app.include_router(threat_jobs)
