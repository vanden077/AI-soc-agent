import logging
from typing import Any

from src.common.cache.driver.redis_driver import RedisDriver

logger = logging.getLogger()


class RedisClient(RedisDriver):
    """
    Redis client implements Redis driver abstract methods.
    Get or insert data to Redis server.
    """

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get data from cache
        :param key: the key to retrieve
        :return: dict[str, Any]|None data stored as dict
                or None if the key is pointing to nothing
        """
        try:
            return self.redis_client.json().get(name=key)
        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache client error while getting key {key}: {err}")
            return None

    def insert(self, key: str, data: dict[str, Any], ttl: int = 3600) -> bool:
        """
        Insert data to cache
        :param key: the key to retrieve data later (like a primary key in SQL)
        :param data: dict[Any, Any] to be saved in cache
                    (basically an object cast into dict)
        :param ttl: how many time data will stay in cache in seconds (default is 3600)
        :return: bool, true if insertion was successful false otherwise
        """
        try:
            result = self.redis_client.json().set(
                name=key, path="$", obj=data, decode_keys=True
            )
            self.redis_client.expire(name=key, time=ttl)
            return bool(result)
        except Exception as err:  # noqa: BLE001
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
            return self.redis_client.delete(key)
        except Exception as err:  # noqa: BLE001
            logger.error(f"Cache client error while deleting key {key}: {err}")
            return 0
