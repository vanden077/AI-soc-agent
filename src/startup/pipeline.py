import logging

from src.constants import Settings
from src.data_pipeline import StixPipeline
from src.embedding.interfaces import IEmbeddingEngine
from src.persistence import PersistenceManager
from src.persistence.interfaces import IVectorIngestionEngine

logger = logging.getLogger(__name__)


def run_pipeline(settings: Settings, embedding_engine: IEmbeddingEngine) -> None:
    """Upsert data to RedisVL."""
    ingestion_engine: IVectorIngestionEngine | None = None
    try:
        logger.info(
            "[PIPELINE STARTUP] Create rw Vector connexion pool to Redis for pipeline ingestion..."
        )
        manager = PersistenceManager(provider=settings.PERSISTENCE_ENGINE)
        ingestion_engine = manager.create_vector_ingestion_engine(
            index_path=settings.MITRE_INDEX_SCHEMA_PATH,
            target_vector_field=settings.REDIS_VL_VECTOR_FIELD,
            semantic_hashes_key=settings.MITRE_SEMANTIC_HASHES_KEY,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            max_size_pool=settings.REDIS_VECTOR_POOL_SIZE,
            retry_strategy=settings.REDIS_RETRY_STRATEGY,
            ssl=settings.REDIS_SSL,
            decode_responses=True,
            db=settings.REDIS_VECTOR_POOL_DB_ID,
        )

        pipeline = StixPipeline(
            cache_client=ingestion_engine,
            embedding_engine=embedding_engine,
            file_path=settings.MITRE_JSON_PATH,
            batch_size=50,
        )

        logger.info(
            "[PIPELINE STARTUP] Running (read/parse/filter/extract/compile/vectorize)..."
        )
        pipeline.run()
        logger.info("[PIPELINE STARTUP] Terminated, data are vectorized and ready.")
    except Exception as e:
        logger.error(f"[PIPELINE STARTUP] Pipeline failed because: {e!s}")
        raise
    finally:
        # Gracefully release connexions
        if ingestion_engine is not None:
            ingestion_engine.close()
