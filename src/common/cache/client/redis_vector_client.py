import logging
from typing import Any, Dict, List, Optional
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery

from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.common.cache.driver.redis_driver import RedisDriver

logger = logging.getLogger()

# TODO work in progress, need to use schema as response
class RedisVectorClient(RedisDriver):
    """
    Redis client dedicated exclusively to hybrid vector search execution.
    Handles automatic log text vectorization internally.
    """

    def __init__(self, embedding_model: IEmbeddingEngine, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.embedding_model = embedding_model  # Injection du modèle (ex: HuggingFaceEmbeddings)
        self.index: Optional[SearchIndex] = None

    def get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def insert(self, key: str, data: dict[str, Any], ttl: int = 3600) -> bool:
        raise NotImplementedError

    def delete(self, key: str) -> int:
        raise NotImplementedError

    def hybrid_search(
            self,
            log_text: str,  # Reçoit le log brut sous forme de chaîne de caractères
            filter_expression: Optional[str] = None,
            limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Vectorizes the input log text and executes a synchronous hybrid search.
        """
        if not self.index:
            logger.error("[-] Hybrid search aborted: RedisVL index wrapper is not set.")
            return []

        try:
            # Centralisation de la vectorisation : invisible pour les routes API
            vector = self.embedding_model.embed_query(log_text)

            query = VectorQuery(
                vector=vector,
                vector_field_name="embedding",
                num_results=limit,
                return_fields=["id", "type", "name", "description", "platforms", "tactics", "vector_distance"],
                filter_expression=filter_expression
            )

            results = self.index.search(query.query, query.params)

            formatted_results = []
            for doc in results.docs:
                platforms = getattr(doc, "platforms", b"")
                tactics = getattr(doc, "tactics", b"")
                name = getattr(doc, "name", b"")
                description = getattr(doc, "description", b"")

                formatted_results.append({
                    "id": getattr(doc, "id", b"").decode(errors="ignore"),
                    "type": getattr(doc, "type", b"").decode(errors="ignore"),
                    "name": name.decode(errors="ignore") if isinstance(name, bytes) else name,
                    "description": description.decode(errors="ignore") if isinstance(description,
                                                                                     bytes) else description,
                    "platforms": platforms.decode(errors="ignore") if isinstance(platforms, bytes) else platforms,
                    "tactics": tactics.decode(errors="ignore") if isinstance(tactics, bytes) else tactics,
                    "distance": float(getattr(doc, "vector_distance", 1.0))
                })
            return formatted_results

        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache client error during hybrid vector search: {err}")
            return []