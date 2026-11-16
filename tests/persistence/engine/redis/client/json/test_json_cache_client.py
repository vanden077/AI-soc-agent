from unittest.mock import patch

from src.persistence.engine.redis.client.json.json_cache_client import JsonCacheClient


def test_redis_client_insert_and_get(json_cache: JsonCacheClient, flush_json_cache):
    """Insert and get a JSON document"""
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    res_insert = json_cache.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = json_cache.get(key=cache_key)
    assert res_get == data


def test_redis_client_get_exception(mocker, json_cache: JsonCacheClient, flush_json_cache, caplog):
    """Make get command crash from driver"""
    redis_mock = mocker.patch(
        "redis.commands.json.commands.JSONCommands.get",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "test"
    data = {"test": "test"}
    ttl = 10
    res_insert = json_cache.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = json_cache.get(key=cache_key)
    assert redis_mock.called
    assert res_get is None
    assert (
        "Cache client error while getting key test: Mocked exception" in caplog.messages
    )


def test_redis_client_insert_exception(mocker, json_cache: JsonCacheClient, caplog):
    """Make set command crash from driver"""
    redis_mock = mocker.patch(
        "redis.commands.json.commands.JSONCommands.set",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "test"
    data = {"test": "test"}
    ttl = 10
    res_insert = json_cache.insert(key=cache_key, data=data, ttl=ttl)
    assert redis_mock.called
    assert res_insert is False
    assert (
        "Cache client error while inserting key test: Mocked exception"
        in caplog.messages
    )


def test_redis_client_delete(json_cache: JsonCacheClient, flush_json_cache):
    """Insert and delete a JSON document"""
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    # add an entry
    res_insert = json_cache.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    # delete it
    res_delete = json_cache.delete(key=cache_key)
    assert res_delete == 1


def test_redis_client_nothing_to_delete(json_cache: JsonCacheClient, flush_json_cache):
    """Check deleting an unexisting document don't crash and return 0 (number of documents deleted)"""
    cache_key = "testeuuuu"
    res_delete = json_cache.delete(key=cache_key)
    assert res_delete == 0


def test_redis_client_delete_exception(mocker, json_cache: JsonCacheClient, caplog):
    """Make delete command crash from driver"""
    redis_mock = mocker.patch(
        "redis.commands.core.BasicKeyCommands.delete",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "testeuuuu"
    res_delete = json_cache.delete(key=cache_key)
    assert redis_mock.called
    assert res_delete == 0
    assert (
        "Cache client error while deleting key testeuuuu: Mocked exception"
        in caplog.messages
    )

def test_redis_client_get_key_none(json_cache: JsonCacheClient, flush_json_cache):
    """Test getting a key of type None don't crash and just return None"""
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    # add an entry
    res_insert = json_cache.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = json_cache.get(key=None)
    assert res_get is None

def test_json_cache_health_delegates_to_driver(json_cache: JsonCacheClient) -> None:
    """Verify health() delegates directly to the underlying driver."""
    with patch.object(json_cache._driver, "health", return_value=True) as mock_health:
        assert json_cache.health() is True
        mock_health.assert_called_once()

def test_json_cache_close_delegates_to_driver(json_cache: JsonCacheClient) -> None:
    """Verify close() delegates connection pool shutdown directly to the underlying driver."""
    with patch.object(json_cache._driver, "close") as mock_close:
        json_cache.close()
        mock_close.assert_called_once()