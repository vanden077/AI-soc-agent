import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.api.dev_setup import configure_dev_helpers
from src.embedding import EmbeddingManager
from src.common.constants import Settings

from src.common.cache import RedisClient, RedisVectorClient

from src.data_pipeline import MitrePipeline

from src.api.routers import health_route


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s:  [APP] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(ai_soc_agent: FastAPI):
    logger.info("⚙️ Load ENV vars into FastAPI context...")
    settings = Settings.model_validate(os.environ)

    logger.info(f"Current environment is: {settings.ENV}")

    # if dev environment, add redirection from / to /docs (=from a 404 to the swagger)
    if settings.ENV == "development":
        configure_dev_helpers(ai_soc_agent)

    logger.info("⚙️ Create connexion pool to Redis for JSON documents...")
    json_cache = RedisClient(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USERNAME,
        password=settings.REDIS_PASSWORD,
        max_size_pool=settings.REDIS_JSON_POOL_SIZE,
        retry_strategy=settings.REDIS_RETRY_STRATEGY,
        ssl=settings.REDIS_SSL,
        decode_responses=True,
        db=settings.REDIS_JSON_POOL_DB_ID
    )

    # start json pool
    json_cache.init_pool()

    # create an instance of the embedding engine based on env vars
    logger.info("⚙️ Create Embedding engine, could take a while, please be patient...")
    emb = EmbeddingManager(provider=settings.EMBEDDING_ENGINE, model_name=settings.EMBEDDING_MODEL_NAME)
    logger.info(f"🚀 Embedding engine {emb.engine.engine_name}, model {emb.engine.model_name} is ready.")

    # create a connexion pool to Redis for vectorized documents
    logger.info("⚙️ Create connexion pool to Redis for vectorized documents...")
    vector_cache = RedisVectorClient(
        embedding_model=emb.engine,
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USERNAME,
        password=settings.REDIS_PASSWORD,
        max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
        retry_strategy=settings.REDIS_RETRY_STRATEGY,
        ssl=settings.REDIS_SSL,
        decode_responses=False,
        db=settings.REDIS_VECTOR_POOL_DB_ID
    )

    # start vector pool
    vector_cache.init_pool()

    # TODO run mitre pipeline at startup + add route to manually call it
    # mitre_pipeline = MitrePipeline(embedding_model=emb.engine, settings=settings)
    # mitre_pipeline.start_pipeline()

    logger.info("🚀 STARTUP COMPLETE")

    # injection into FastAPI context
    yield {
        "settings": settings,
        "embedding_engine": emb.engine,
        "json_cache": json_cache,
        "vector_cache": vector_cache
    }

    if json_cache is not None:
        json_cache.close()

    if vector_cache is not None:
        vector_cache.close()

    logger.info("👋 Gracefully closed app... Bye")

app = FastAPI(title="AI Soc agent.", lifespan=lifespan)
app.include_router(health_route)
