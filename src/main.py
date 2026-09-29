import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.dev_setup.setup import configure_dev_helpers
from schemas import Settings

from shared.cache import RedisClient
from src.api.routers.health import health_route

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s:  [APP] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("⚙️ Load ENV vars into FastAPI context...")
    settings = Settings.model_validate(os.environ)

    logger.info("⚙️ Create connexion pool to Redis for JSON documents...")
    json_cache = RedisClient(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USERNAME,
        password=settings.REDIS_PASSWORD,
        max_size_pool=settings.REDIS_JSON_POOL_SIZE,
        retry_strategy=settings.REDIS_RETRY_STRATEGY,
        ssl=settings.REDIS_SSL,
        decode_responses=True
    )

    # start json pool
    json_cache.init_pool()

    # create a connexion pool to Redis for vectorized documents
    logger.info("⚙️ Create connexion pool to Redis for vectorized documents...")
    vector_cache = RedisClient(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USERNAME,
        password=settings.REDIS_PASSWORD,
        max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
        retry_strategy=settings.REDIS_RETRY_STRATEGY,
        ssl=settings.REDIS_SSL,
        decode_responses=False
    )

    # start vector pool
    vector_cache.init_pool()

    logger.info("🚀 STARTUP COMPLETE 🚀")

    # injection into FastAPI context
    yield {
        "settings": settings,
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

# if dev environment, add redirection from / to /docs (=from a 404 to the swagger)
if os.getenv("ENV") == "development":
    configure_dev_helpers(app)