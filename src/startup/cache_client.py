import logging

from src.common.cache import VectorCacheClient
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.common.constants import Settings
from src.common.cache import JsonCacheClient
logger = logging.getLogger(__name__)

def init_json_pool(settings: Settings) -> JsonCacheClient:
    """Create a cache client for JSON documents holding an isolated connexion pool"""
    try:
        json_cache = JsonCacheClient(
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
        json_cache.init_pool()
        return json_cache
    except Exception as e:
        logger.error("Creating cache client specialized in JSON documents, "
                     f"on {settings.REDIS_HOST}:{settings.REDIS_PORT}, "
                     f"db: {settings.REDIS_JSON_POOL_DB_ID}, "
                     f"failed because: {str(e)}")
        raise e

def init_vector_pool(settings: Settings, embedding_engine: IEmbeddingEngine) -> VectorCacheClient:
    """Create a cache client for VECTOR documents holding an isolated connexion pool"""
    try:
        vector_cache = VectorCacheClient(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=settings.REDIS_RETRY_STRATEGY,
            ssl=settings.REDIS_SSL,
            decode_responses=False,
            db=settings.REDIS_VECTOR_POOL_DB_ID,
            embedding_engine=embedding_engine,
            index_path=settings.MITRE_INDEX_SCHEMA_PATH,
        )
        vector_cache.init_pool()
        vector_cache.sync_lifespan_catalog()
        return vector_cache
    except Exception as e:
        logger.error("Creating cache client specialized in VECTOR documents, "
                     f"on {settings.REDIS_HOST}:{settings.REDIS_PORT}, "
                     f"db: {settings.REDIS_VECTOR_POOL_DB_ID} "
                     f"failed because: {str(e)}")
        raise e
