from typing import Any

from src.persistence.engine.redis.client.json.json_cache_client import JsonCacheClient
from src.persistence.engine.redis.client.vector.ingestion_cache_client import (
    IngestionCacheClient,
)
from src.persistence.engine.redis.client.vector.vector_cache_client import (
    VectorCacheClient,
)
from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.interfaces.i_json_storage_engine import IJsonStorageEngine
from src.persistence.interfaces.i_persistence_factory import IPersistenceFactory
from src.persistence.interfaces.i_vector_ingestion_engine import IVectorIngestionEngine
from src.persistence.interfaces.i_vector_search_engine import IVectorSearchEngine


class RedisPersistenceFactory(IPersistenceFactory):
    """
    Concrete persistence factory encapsulating Redis driver wiring,
    RESP2/RESP3 protocol isolation, and connection pool lifecycle.
    """

    def create_json_engine(self, **kwargs: Any) -> IJsonStorageEngine:
        """Instantiate and initialize an isolated Redis JSON storage engine (RESP3)."""
        driver = RedisDriver(**kwargs, vector_capability=False)
        driver.init_pool()
        return JsonCacheClient(driver=driver)

    def create_vector_search_engine(
        self,
        index_path: str,
        **kwargs: Any,
    ) -> IVectorSearchEngine:
        """Instantiate and initialize a read-only RedisVL vector search engine (RESP2)."""
        driver = RedisDriver(**kwargs, vector_capability=True)
        driver.init_pool()
        try:
            client = VectorCacheClient(driver=driver, index_path=index_path)
            client.sync_lifespan_catalog()
            return client
        except Exception:
            # cleanup connections if catalog can't be synchronized
            driver.close()
            raise

    def create_vector_ingestion_engine(
        self,
        index_path: str,
        target_vector_field: str,
        semantic_hashes_key: str,
        **kwargs: Any,
    ) -> IVectorIngestionEngine:
        """Instantiate and initialize an ephemeral RedisVL batch ingestion engine (RESP2)."""
        driver = RedisDriver(**kwargs, vector_capability=True)
        driver.init_pool()
        try:
            client = IngestionCacheClient(
                driver=driver,
                target_vector_field=target_vector_field,
                semantic_hashes_key=semantic_hashes_key,
            )
            client.init_search_index(schema_path=index_path)
            return client
        except Exception:
            # cleanup connections if search index can't be initiated
            driver.close()
            raise
