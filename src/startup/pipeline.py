import logging

from common.cache import IngestionCacheClient
from data_pipeline import StixPipeline
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.common.constants import Settings
logger = logging.getLogger(__name__)

def run_pipeline(settings: Settings, embedding_engine: IEmbeddingEngine):
    """Upsert data to RedisVL"""
    ingestion_cache_client = None
    try:
        logger.info("⚙️ Create rw Vector connexion pool to Redis for pipeline ingestion...")
        ingestion_cache_client = IngestionCacheClient(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=settings.REDIS_RETRY_STRATEGY,
            ssl=settings.REDIS_SSL,
            decode_responses=True,
            db=settings.REDIS_VECTOR_POOL_DB_ID,
            target_vector_field=settings.REDIS_VL_VECTOR_FIELD,
            semantic_hashes_key=settings.MITRE_SEMANTIC_HASHES_KEY,
        )

        # init connexions pool
        ingestion_cache_client.init_pool()
        # init RedisVL search index
        logger.info("Plumbing: Binding RedisVL SearchIndex Schema layout to ingestion cache client...")
        ingestion_cache_client.init_search_index(schema_path=settings.MITRE_INDEX_SCHEMA_PATH)

        pipeline = StixPipeline(
            cache_client=ingestion_cache_client,
            embedding_engine=embedding_engine,
            file_path=settings.MITRE_JSON_PATH,
            batch_size=50
        )

        logger.info("⚙️ Start pipeline (read/parse/filter/extract/compile/vectorize)...")
        pipeline.run()
        logger.info(f"🚀 Pipeline terminated, data are vectorized and ready.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed because: {str(e)}")
        raise e
    finally:
        # Gracefully release connexions
        if ingestion_cache_client is not None:
            ingestion_cache_client.close()
