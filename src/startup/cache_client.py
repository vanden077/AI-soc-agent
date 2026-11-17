import logging

from src.constants import Settings
from src.persistence import PersistenceManager
from src.persistence.interfaces import IJsonStorageEngine, IVectorSearchEngine

logger = logging.getLogger(__name__)


def init_json_pool(settings: Settings) -> IJsonStorageEngine:
    """Create a persistence client for JSON documents holding an isolated connexion pool."""
    try:
        logger.info("[JSON POOL STARTUP] Init pool...")
        manager = PersistenceManager(provider=settings.PERSISTENCE_ENGINE)
        return manager.create_json_engine(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            max_size_pool=settings.REDIS_JSON_POOL_SIZE,
            retry_strategy=settings.REDIS_RETRY_STRATEGY,
            ssl=settings.REDIS_SSL,
            decode_responses=True,
            db=settings.REDIS_JSON_POOL_DB_ID,
        )
    except Exception as e:
        logger.error(
            "[JSON POOL STARTUP] Creating persistence client specialized in JSON documents, "
            f"on {settings.REDIS_HOST}:{settings.REDIS_PORT}, "
            f"db: {settings.REDIS_JSON_POOL_DB_ID}, "
            f"failed because: {e!s}"
        )
        raise


def init_vector_pool(settings: Settings) -> IVectorSearchEngine:
    """Create a persistence client for VECTOR documents holding an isolated connexion pool."""
    try:
        logger.info("[VECTOR POOL STARTUP] Init pool...")
        manager = PersistenceManager(provider=settings.PERSISTENCE_ENGINE)
        return manager.create_vector_search_engine(
            index_path=settings.MITRE_INDEX_SCHEMA_PATH,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=settings.REDIS_RETRY_STRATEGY,
            ssl=settings.REDIS_SSL,
            decode_responses=False,
            db=settings.REDIS_VECTOR_POOL_DB_ID,
        )
    except Exception as e:
        logger.error(
            "[VECTOR POOL STARTUP] Creating persistence client specialized in VECTOR documents, "
            f"on {settings.REDIS_HOST}:{settings.REDIS_PORT}, "
            f"db: {settings.REDIS_VECTOR_POOL_DB_ID} "
            f"failed because: {e!s}"
        )
        raise
