import logging
from typing import Any

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redisvl.index import SearchIndex

from src.persistence.engine.redis.driver.vector_fields_specs import VectorFieldSpecs

logger = logging.getLogger()


class RedisDriver:
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
            db: int = 0,
            vector_capability: bool = False,
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
        self._vector_capability = vector_capability
        # self._client is available after calling init_pool()
        self._client: Redis | None = None
        # self._search_index is available only if driver has vector capabilities, and after calling init_search_index()
        self._search_index: SearchIndex | None = None

    # ============================================================================
    # COMMON FUNCTIONS / LIFECYCLE
    # ============================================================================
    def init_pool(self) -> None:
        """
        Create a connection pool based on instance variables.
        Must be explicitly called after driver instantiation.
        :return: None
        """
        if self._client is not None:
            return

        # ARCHITECTURAL NOTE:
        # RediSearch (`FT.SEARCH`) inside `redisvl==0.27.2` expects RESP2 `Result` objects
        # exposing `.docs`. Enabling RESP3 (`protocol=3`) causes `redis-py` to return raw
        # dicts instead, crashing `SearchIndex.query()`. Keep RESP3 for JSON pools, enforce
        # RESP2 on vector search pools.
        redis_protocol = 2 if self._vector_capability else 3

        try:
            self._client = Redis(
                max_connections=self._max_size_pool,
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                decode_responses=self._decode_responses,
                protocol=redis_protocol,
                retry=self._retry,
                ssl=self._ssl,
                db=self._db,
            )

            logger.info(
                "Cache pool created successfully, "
                f"Max connections: {self.pool_size}, "
                f"Retry strategy: {self._retry_strategy}"
            )
        except Exception as err:
            logger.error(f"Cache pool is KO because: {err}")
            raise

    def health(self) -> bool:
        """
        Health check
        :return: bool, True if server is ready, else false
        """
        try:
            return bool(self.redis_client.ping())
        except Exception as err:
            logger.error(f"Error something went wrong, cant ping Cache server: {err}")
            return False

    def flush_db(self) -> None:
        """
        https://redis.io/docs/latest/commands/flushdb/
        Delete all keys of the current database
        :return: None
        """
        self.redis_client.flushdb()

    def close(self) -> None:
        """
        Release all pool connections, and shutdown pool.
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
        if self._client is None:
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
        if self._client is None:
            return 0

        return int(self.redis_client.connection_pool.max_connections)  # type: ignore[arg-type]

    @property
    def retry_strategy(self) -> int:
        """
        Return retry strategy (= how many attempts to connect to Redis before giving up)
        :return: int
        """
        return self._retry_strategy

    @property
    def decode_responses(self) -> bool:
        """
        Return whether the underlying Redis client automatically decodes bytes to strings.
        :return: bool, True if auto-decoding is enabled, False otherwise.
        """
        return self._decode_responses

    # ============================================================================
    # KEY LISTING
    # ============================================================================
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
        :return: the number of keys in Redis and the entire list of keys as str
        """
        result = []
        cursor = 0

        try:
            while True:
                cursor, batch_keys = self.redis_client.scan(
                    cursor=cursor, match=match, count=batch_size
                )
                result.extend(batch_keys)
                if cursor == 0:
                    break
        except Exception as err:
            logger.error(f"Cache client error while listing keys: {err}")

        # cast key type to str if needed
        if result:
            if isinstance(result[0], bytes):
                result = [key.decode() for key in result]
            elif not isinstance(result[0], str):
                result = [str(key) for key in result]

        return len(result), result

    # ============================================================================
    # VECTOR CAPABILITIES
    # ============================================================================
    def init_search_index(self, schema_path: str) -> None:
        """
        Binds a Redis VL SearchIndex instance to the driver.
        If the index do not already exists in self._db, then it is created.
        Must be explicitly called after pool instantiation.

        Lifecycle:
        1-instantiate this driver.
        2-instantiate its pool (init_pool)
        3-instantiate search_index (init_search_index)

        :param schema_path: path to a YAML file containing
        :raises: RuntimeError | ValueError | TypeError
        """
        if not self._vector_capability:
            raise RuntimeError(
                "Critical: This persistence client instance was initialized without vector capabilities."
            )

        if not schema_path or not schema_path.strip():
            raise ValueError(
                "Critical: path to RediVL index schema cannot be None or empty."
            )

        try:
            index_builder = SearchIndex.from_yaml(
                schema_path=schema_path,
                redis_client=self.redis_client,
                validate_on_load=True,
                owns_client=False,
                # critical, if set to True, we delegate client lifecycle (so connection pool lifecycle)
                # to this object, here we want to keep full control on it.
            )

            if not index_builder.exists():
                index_builder.create(overwrite=False)
        except (ValueError, TypeError, RuntimeError) as err:
            logger.error(f"Error while creating search index from {schema_path}: {err}")
            raise

        self._search_index = index_builder

    def get_index_metadata_fields(self) -> set[str]:
        """
        Extracts all human-readable metadata field names (e.g., 'text', 'tag', 'numeric')
        from the loaded RedisVL index schema, excluding technical vector tensor columns.
        """
        schema_data = self.search_index.schema.model_dump(mode="json")
        return {
            field_name
            for field_name, field_info in schema_data.get("fields", {}).items()
            if field_info.get("type") != "vector"
        }

    def get_index_vector_fields_catalog(self) -> dict[str, VectorFieldSpecs]:
        """
        Extracts all vector field specifications from the loaded RedisVL index schema.

        ARCHITECTURAL NOTE / VERSION LOCK:
        This implementation directly accesses the typed Pydantic structure of `VectorField`
        as defined in `redisvl==0.27.2` (pinned in `pyproject.toml`). Upstream RedisVL releases
        frequently introduce breaking changes to internal schema models; portability to newer
        versions is intentionally not guaranteed without updating this adapter.
        """
        vector_catalog: dict[str, VectorFieldSpecs] = {}
        schema_data = self.search_index.schema.model_dump(mode="json")

        for field_name, field_info in schema_data.get("fields", {}).items():
            if field_info.get("type") == "vector":
                attrs = field_info.get("attrs", {})
                vector_catalog[field_name] = VectorFieldSpecs(
                    name=field_name,
                    dimension=int(attrs["dims"]),
                    metric=str(attrs["distance_metric"]).lower(),
                    algorithm=str(attrs["algorithm"]).lower(),
                    source_path=str(field_info.get("path") or field_name),
                )

        if not vector_catalog:
            raise ValueError(
                "Invalid index configuration: No explicit vector field detected. "
                "Please check the index YAML file; it must contain at least one vector field."
            )

        return vector_catalog

    def get_index_prefix(self) -> str:
        """
        Return the index prefix defined in the Redis VL schema (YAML file).
        This prefix is used to build unique identifier in database, prefix:id
        """
        raw_prefix: str = self.search_index.schema.index.prefix
        return raw_prefix if raw_prefix.endswith(":") else f"{raw_prefix}:"

    @property
    def search_index(self) -> Any:
        """
        Transparently exposes the active Redis VL SearchIndex instance.
        """
        if not self._vector_capability:
            raise RuntimeError(
                "This persistence client instance was initialized without vector capabilities."
            )

        if self._search_index is None:
            raise RuntimeError("Search index has not been loaded into the driver yet.")
        return self._search_index
