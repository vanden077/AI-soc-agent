import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.persistence.interfaces import IJsonStorageEngine, IVectorSearchEngine
from src.llm.interfaces import ILlmEngine
from src.embedding.interfaces import IEmbeddingEngine
from src.api.dev_setup import configure_dev_helpers
from src.constants import Settings

from src.api.routers import health_route, threat_analyzer
from src.startup import load_env_vars, init_embedding_engine, run_pipeline, init_llm, init_json_pool, init_vector_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s:  [APP] %(message)s"
)

noisy_loggers = [
    "langchain",
    "langchain_core",
    "langchain_community",
    "ollama",
    "httpx",
    "httpcore",
    "redisvl"
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
    # PHASE 2: Initialize embedding engine, and push its instance into context
    # ==============================================================================
    embedding_engine: IEmbeddingEngine = init_embedding_engine(settings=settings)

    # ==============================================================================
    # PHASE 3: Check mitre_attack_v1 vector database integrity
    # ==============================================================================
    run_pipeline(settings=settings, embedding_engine=embedding_engine)

    json_cache = None
    vector_cache = None

    try:
        # ==============================================================================
        # PHASE 4: Prepare connexions pools for runtime, and push instances into context
        # ==============================================================================
        json_cache: IJsonStorageEngine = init_json_pool(settings=settings)
        vector_cache: IVectorSearchEngine = init_vector_pool(settings=settings)

        # ==============================================================================
        # PHASE 5: Initialize LLM engine, and push its instance into context
        # ==============================================================================
        llm_engine: ILlmEngine = init_llm(settings=settings)

        logger.info("🚀 STARTUP COMPLETE")

        # injections into FastAPI context
        yield {
            "settings": settings,
            "embedding_engine": embedding_engine,
            "llm_engine": llm_engine,
            "json_cache": json_cache,
            "vector_cache": vector_cache
        }
    finally:
        # Gracefully release json persistence connexions pool
        if json_cache is not None:
            json_cache.close()
        # Gracefully release vector persistence connexions pool
        if vector_cache is not None:
            vector_cache.close()

    logger.info("👋 Gracefully closed app... Bye")

app = FastAPI(title="AI Soc agent.", lifespan=lifespan)
app.include_router(health_route)
app.include_router(threat_analyzer)
