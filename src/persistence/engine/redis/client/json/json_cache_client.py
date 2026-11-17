import logging
from collections.abc import Mapping
from typing import Any

from src.persistence.engine.redis.driver.redis_driver import RedisDriver
from src.persistence.interfaces.i_json_storage_engine import IJsonStorageEngine

logger = logging.getLogger()


class JsonCacheClient(IJsonStorageEngine):
    """
    Redis client for JSON documents.
    """

    def __init__(self, driver: RedisDriver) -> None:
        self._driver = driver

    def get(
        self, key: str
    ) -> str | int | float | bool | None | Mapping[str, Any] | list[Any]:
        """
        Get data from persistence
        :param key: the key to retrieve
        :return: dict[str, Any]|None data stored as dict
                or None if the key is pointing to nothing
        """
        try:
            return self._driver.redis_client.json().get(name=key)
        except Exception as err:
            logger.error(f"Cache client error while getting key {key}: {err}")
            return None

    def insert(self, key: str, data: dict[str, Any], ttl: int = 3600) -> bool:
        """
        Insert data to persistence
        :param key: the key to retrieve data later (like a primary key in SQL)
        :param data: dict[Any, Any] to be saved in persistence
                    (basically an object cast into dict)
        :param ttl: how many time data will stay in persistence in seconds (default is 3600)
        :return: bool, true if insertion was successful false otherwise
        """
        try:
            result = self._driver.redis_client.json().set(
                name=key, path="$", obj=data, decode_keys=True
            )
            self._driver.redis_client.expire(name=key, time=ttl)
            return bool(result)
        except Exception as err:
            logger.error(f"Cache client error while inserting key {key}: {err}")
            return False

    def delete(self, key: str) -> int:
        """
        Delete a Redis entry identified by its key.
        You need to implement your own Redis client based on this driver and your needs.
        Removes the specified keys. A key is ignored if it does not exist.
        :param key:str the key you want to delete
        :return: number of deleted entries
        """
        try:
            return self._driver.redis_client.delete(key)
        except Exception as err:
            logger.error(f"Cache client error while deleting key {key}: {err}")
            return 0

    def health(self) -> bool:
        """
        Health check
        :return: bool, True if server is ready, else false
        """
        return self._driver.health()

    def close(self) -> None:
        """
        Release all connections on app shutdown event
        :return: None
        """
        self._driver.close()
