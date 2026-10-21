import logging
from abc import ABC
from typing import Any, Optional, TYPE_CHECKING
from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from src.common.cache.driver.vector_fields_specs import VectorFieldSpecs

logger = logging.getLogger()

# only for linters
if TYPE_CHECKING:
    from redisvl.index import SearchIndex

class RedisDriver(ABC):
    """
    Redis driver handling a connection pool and retry mechanism
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        ssl: bool = True,
        username: str | None = None,
        password: str | None = None,
        max_size_pool: int = 50,
        retry_strategy: int = 3,
        decode_responses: bool = True,
        db: int = 0
    ):
        self._host = "localhost" if host is None else host
        self._port = 6379 if port is None else port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._max_size_pool = max_size_pool
        self._retry_strategy = retry_strategy
        self._retry = Retry(ExponentialBackoff(cap=1, base=0.2), retry_strategy)
        self._decode_responses = decode_responses
        self._db = db
        self._client: Redis
        self._index: Optional["SearchIndex"]

    def set_search_index(self, index_name: str) -> None:
        """
        Binds a Redis VL SearchIndex instance to the driver during lifespan boot.
        Allows the driver to take ownership of the index lifecycle.
        """
        if not index_name or not index_name.strip():
            raise ValueError("The provided SearchIndex cannot be None.")

        # LAZY IMPORT: prevent access from search_index if the calling client is not waiting for vector requests
        from redisvl.index import SearchIndex

        self._index = SearchIndex.from_existing(
            name=index_name.strip(),
            redis_client=self.redis_client
        )

    def get_index_fields(self) -> list[str]:
        """
        [METADATA RETURN FIELDS]
        Extracts the complete list of all attribute names declared in the Redis VL schema.

        RAG / Agent Role:
            Defines ALL textual or contextual data that Redis must load and return
            to the Agent after finding the relevant documents.

        SQL Analogy:
            Equivalent to listing the columns in: "SELECT id, name, description, tactics..."

        Technical Destination:
            Feeds the 'return_fields' argument in the VectorQuery construction.
        """
        return list(self.search_index.schema.fields.keys())

    def get_index_vector_fields_catalog(self) -> dict[str, VectorFieldSpecs]:
        """
        [VECTOR COMPUTATION FIELD]
        Dynamically identifies all fields of type "VectorField" within the index schema.

        RAG / Agent Role:
            Specifies the exact location of the mathematical coordinates (embeddings) in the database.
            Redis will execute the similarity calculation (KNN) exclusively on this column
            against the vectorized query text provided by the Agent.

        SQL Analogy:
            Equivalent to designating the target column in a mathematical clause:
            "WHERE DISTANCE(agent_query_vector, database.vector_column)".

        Technical Destination:
            Feeds the 'vector_field_names' argument in the VectorQuery construction.
        """
        # FAIL-FAST 1: check schema is effectively loaded
        if not self.search_index.schema.fields:
            raise RuntimeError(f"Search index schema '{self.search_index.name}' is empty."
            )

        # Build an auto-documented catalog of immutable specs
        vector_catalog = {
            field_name: VectorFieldSpecs(
                name=field_name,
                dimension=field_obj.dimension,
                metric=field_obj.metric,
                algorithm=field_obj.algorithm,
                source_path=field_obj.path if field_obj.path else field_name
            )
            for field_name, field_obj in self.search_index.schema.vector_fields.items()
        }

        # FAIL-FAST 2: Prevent the client from running with a broken schema
        if not vector_catalog:
            raise ValueError(
                f"Invalid index configuration: No explicit vector field detected in the schema "
                f"for index '{self.search_index.name}'."
            )

        return vector_catalog

    def list_keys(
        self, match: str | None = None, batch_size: int = 500
    ) -> tuple[int, list[str]]:
        """
        https://redis.io/docs/latest/commands/scan/
        Entirely scan Redis keyspace.
        Be aware that this could be violent for large batches
        and can block other Redis operations.

        :param match: A matching pattern to look for specific keys, example: <user_*>
        :param batch_size: The size of keys returned for each call to Redis
        :return: the number of keys in Redis and the entire list of keys as bytes
        (you can loop over the list with .decode("utf-8") to cast each row as string)
        """
        result = []

        try:
            # first call, cursor starts to 0
            cursor, batch_keys = self.redis_client.scan(
                cursor=0, match=match, count=batch_size
            )
            result.extend(batch_keys)
            while cursor != 0:
                cursor, batch_keys = self.redis_client.scan(
                    cursor=cursor,
                    match=match,
                    count=batch_size,
                )
                result.extend(batch_keys)
        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache client error while listing keys: {err}")

        # cast key type to str if needed
        if result:
            if isinstance(result[0], bytes):
                result = [key.decode() for key in result]
            elif not isinstance(result[0], str):
                result = [str(key) for key in result]

        return len(result), result

    def health(self) -> bool:
        """
        Health check
        :return: bool, True if server is ready, else false
        """
        try:
            return bool(self.redis_client.ping())
        except Exception as err:  # noqa: BLE001
            logger.error(f"Error something went wrong, cant ping Cache server: {err}")
            return False

    def flush_db(self) -> None:
        """
        https://redis.io/docs/latest/commands/flushdb/
        Delete all keys of the current database
        :return: None
        """
        self.redis_client.flushdb()

    def init_pool(self) -> None:
        """
        Create a connection pool based on instance variables
        :return: None
        """
        if hasattr(self, "_client"):
            return

        try:
            self._client = Redis(
                max_connections=self._max_size_pool,
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                decode_responses=self._decode_responses,
                protocol=3,
                retry=self._retry,
                ssl=self._ssl,
                db=self._db,
            )

            logger.info(
                "Cache pool created successfully, "
                f"Max connections: {self.pool_size}, "
                f"Retry strategy: {self._retry_strategy}"
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache pool is KO because: {err}")
            raise err

    def close(self) -> None:
        """
        Release all connections on app shutdown event
        :return: None
        """
        self.redis_client.close()

    @property
    def redis_client(self) -> Redis:
        """
        Return Redis instance.
        All Redis operations (adding, getting, deleting etc...)
        are based on this instance.

        :raises: RuntimeError (if init_pool has not been called)
        :return: Redis instance.
        """
        if not hasattr(self, "_client"):
            raise RuntimeError(
                "Critical: pool connexion is not initialized, please call init_pool before performing Redis operations."
            )

        return self._client

    @property
    def host(self) -> str:
        """
        Return Redis host
        :return: str
        """
        return self._host

    @property
    def port(self) -> int:
        """
        Return Redis port
        :return: int
        """
        return self._port

    @property
    def pool_size(self) -> int:
        """
        Return Redis connection pool size
        :return: int
        """
        # don't raise here, just tell there is no connexions
        if not hasattr(self, "_client"):
            return 0

        return int(self.redis_client.connection_pool.max_connections) # type: ignore[arg-type]

    @property
    def retry_strategy(self) -> int:
        """
        Return retry strategy (= how many attempts to connect to Redis before giving up)
        :return: int
        """
        return self._retry_strategy

    @property
    def search_index(self) -> Any:
        """
        Transparently exposes the active Redis VL SearchIndex instance.
        """
        if not hasattr(self, "_index"):
            raise RuntimeError("Search index has not been loaded into the driver yet.")
        return self._index
