import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.api.dev_setup import configure_dev_helpers
from src.common.constants import Settings
from src.common.cache import JsonCacheClient, VectorCacheClient

from src.api.routers import health_route
from src.startup import load_env_vars, init_embedding_engine, run_pipeline, init_json_pool, init_vector_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s:  [APP] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(ai_soc_agent: FastAPI):
    """
    If anything crash here, service can't be healthy, we just let it crash for deeper investigation.
    """
    settings: Settings = load_env_vars()

    # redirection from / to /docs
    if settings.ENV == "development":
        configure_dev_helpers(ai_soc_agent)

    embedding_engine: IEmbeddingEngine = init_embedding_engine(settings=settings)

    # =========================================================================
    # PHASE 1: Check mitre_attack_v1 vector database integrity
    # =========================================================================
    run_pipeline(settings=settings, embedding_engine=embedding_engine)

    # =========================================================================
    # PHASE 2: Prepare connexions pools for runtime
    # =========================================================================
    json_cache = None
    vector_cache = None

    try:
        json_cache: JsonCacheClient = init_json_pool(settings=settings)
        vector_cache: VectorCacheClient = init_vector_pool(settings=settings, embedding_engine=embedding_engine)
        logger.info("🚀 STARTUP COMPLETE")

        # injection into FastAPI context
        yield {
            "settings": settings,
            "embedding_engine": embedding_engine,
            "json_cache": json_cache,
            "vector_cache": vector_cache
        }
    finally:
        # Gracefully release json cache connexions pool
        if json_cache is not None:
            json_cache.close()
        # Gracefully release vector cache connexions pool
        if vector_cache is not None:
            vector_cache.close()

    logger.info("👋 Gracefully closed app... Bye")

app = FastAPI(title="AI Soc agent.", lifespan=lifespan)
app.include_router(health_route)
