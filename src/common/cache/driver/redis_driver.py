import logging
from abc import ABC, abstractmethod
from typing import Any

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

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
        decode_responses: bool = True
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
        self._client: Redis | None = None

    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None:  # pragma: no cover
        """
        https://redis.io/docs/latest/commands/json.get/
        Get data from Redis cache.
        You need to implement your own Redis client based on this driver and your needs.
        :param key:str the key you want to get
        :return: dict[str, Any]|None data stored as dict
                or None if the key is pointing to nothing
        """

    @abstractmethod
    def insert(
        self, key: str, data: dict[str, Any], ttl: int = 3600
    ) -> bool:  # pragma: no cover
        """
        https://redis.io/docs/latest/commands/json.set/
        Insert data into Redis cache
        You need to implement your own Redis client based on this driver and your needs.
        :param key: str the key to retrieve data later (like a primary key in SQL)
        :param data: dict[str, Any] as dict to be saved in cache
        :param ttl: int how many time data will stay in cache in seconds
        :return: bool, true if insertion was successful false otherwise
        """

    @abstractmethod
    def delete(self, key: str) -> int:  # pragma: no cover
        """
        https://redis.io/docs/latest/commands/del/
        Delete a Redis entry identified by its key.
        You need to implement your own Redis client based on this driver and your needs.
        Removes the specified keys. A key is ignored if it does not exist.
        :param key:str the key you want to delete
        :return: number of deleted entries
        """

    def list_keys(
        self, match: str | None = None, batch_size: int = 500
    ) -> tuple[int, list[str]]:
        """
        https://redis.io/docs/latest/commands/scan/
        Entirely scan Redis keyspace.
        Be aware that this could be violent for large batches
        and can block other Redis operations.

        :param match: A matching pattern to look for specific keys, example: <user_*>
        :param batch_size: The size of keys returned for each call to redis
        :return: the number of keys in Redis and the entire list of keys as bytes
        (you can loop over the list with .decode("utf-8") to cast each row as string)
        """
        self.init_pool()
        result = []

        try:
            # first call, cursor starts to 0
            cursor, batch_keys = self._client.scan(
                cursor=0, match=match, count=batch_size
            )
            result.extend(batch_keys)
            while cursor != 0:
                cursor, batch_keys = self._client.scan(
                    cursor=cursor,
                    match=match,
                    count=batch_size,
                )
                result.extend(batch_keys)
        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache client error while listing keys: {err}")

        # convert key type to str if needed
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
            self.init_pool()
            return bool(self._client.ping())
        except Exception as err:  # noqa: BLE001
            logger.error(f"Error something went wrong, cant ping Cache server: {err}")
            return False

    def flushdb(self) -> None:
        """
        https://redis.io/docs/latest/commands/flushdb/
        Delete all keys of the current database
        :return: None
        """
        if self._client is not None:
            self._client.flushdb()

    def init_pool(self) -> None:
        """
        Create a connection pool based on instance variables
        :return: None
        """
        if self._client is None:
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
                )
                # ping server to be sure that the connection is really established
                self._client.ping()
                logger.info(
                    f"Cache pool created successfully, "
                    f"Max connections: {self._client.connection_pool.max_connections}, "
                    f"Retry strategy: {self._retry_strategy}"
                )
            except Exception as err:  # noqa: BLE001
                self._client = None
                logger.error(f"Cache pool is KO because: {err}")

    def close(self) -> None:
        """
        Release all connections on app shutdown event
        :return: None
        """
        if self._client is not None:
            self._client.close()

    @property
    def redis_client(self) -> Redis | None:
        """
        Return Redis instance.
        All Redis operations (adding, getting, deleting etc...)
        are based on this instance.
        :return: Redis instance.
        """
        self.init_pool()
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
        if self._client is not None:
            return int(self._client.connection_pool.max_connections)
        return 0

    @property
    def retry_strategy(self) -> int:
        """
        Return retry strategy (= how many attempts to connect to redis before giving up)
        :return: int
        """
        return self._retry_strategy
