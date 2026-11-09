import logging
from abc import ABC
from typing import Any
from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redisvl.index import SearchIndex
from src.common.cache.driver.vector_fields_specs import VectorFieldSpecs

logger = logging.getLogger()

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
        except Exception as err:  # noqa: BLE001
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
                "Critical: This cache client instance was initialized without vector capabilities."
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
                owns_client=False
                # critical, if set to True, we delegate client lifecycle (so connection pool lifecycle)
                # to this object, here we want to keep full control on it.
            )

            if not index_builder.exists():
                index_builder.create(overwrite=False)
        except (ValueError, TypeError, RuntimeError) as err:
            logger.error(f"Error while creating search index from {schema_path}: {err}")
            raise err

        self._search_index = index_builder

    def get_index_fields(self) -> list[str]:
        """
        Dynamically identifies all fields of type "text" or "tag" within the index schema.
        """
        return list(self.search_index.schema.fields.keys())

    def get_index_vector_fields_catalog(self) -> dict[str, VectorFieldSpecs]:
        """
        Dynamically identifies all fields of type "vector" within the index schema,
        guaranteeing the exact dict[str, VectorFieldSpecs] return layout contract.

        I don't like doing that, but it's a fallback against chaotic breaking changes in redis-py.
        It's better to get everything through properties, but it's currently impossible as redis-py devs
        constantly add nested objects to already nested objects.
        """
        vector_catalog: dict[str, VectorFieldSpecs] = {}

        # Iterate through the unified fields dictionary provided by RedisVL
        for field_name, field_obj in self.search_index.schema.fields.items():
            # Identify vector fields by checking their type attribute string
            field_type = str(getattr(field_obj, "type", "")).lower()

            if field_type == "vector":
                # In RedisVL v0.27.2, vector field properties are located inside the field_obj directly
                # or nested under its properties. We extract them via safe fallback attributes.
                dimension = getattr(field_obj, "dimension", getattr(field_obj, "dims", 0))
                metric = getattr(field_obj, "metric", "cosine")
                algorithm = getattr(field_obj, "algorithm", "hnsw")
                source_path = getattr(field_obj, "path", field_name) if getattr(field_obj, "path", None) else field_name

                # Hydrate your concrete custom VectorFieldSpecs object exactly as expected
                vector_catalog[field_name] = VectorFieldSpecs(
                    name=field_name,
                    dimension=int(dimension),
                    metric=str(metric).lower(),
                    algorithm=str(algorithm).lower(),
                    source_path=str(source_path)
                )

        if not vector_catalog:
            raise ValueError("Invalid index configuration: No explicit vector field detected, "
                             "please check index yaml file, it should contains at least one vector field.")

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
            raise RuntimeError("This cache client instance was initialized without vector capabilities.")

        if self._search_index is None:
            raise RuntimeError("Search index has not been loaded into the driver yet.")
        return self._search_index
