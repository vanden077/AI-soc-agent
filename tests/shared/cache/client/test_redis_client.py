def test_redis_client_insert_and_get(redis, flush_cache):
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    res_insert = redis.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = redis.get(key=cache_key)
    assert res_get == data


def test_redis_client_get_exception(mocker, redis, flush_cache, caplog):
    redis_mock = mocker.patch(
        "redis.commands.json.commands.JSONCommands.get",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "test"
    data = {"test": "test"}
    ttl = 10
    res_insert = redis.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = redis.get(key=cache_key)
    assert redis_mock.called
    assert res_get is None
    assert (
        "Cache client error while getting key test: Mocked exception" in caplog.messages
    )


def test_redis_client_insert_exception(mocker, redis, caplog):
    redis_mock = mocker.patch(
        "redis.commands.json.commands.JSONCommands.set",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "test"
    data = {"test": "test"}
    ttl = 10
    res_insert = redis.insert(key=cache_key, data=data, ttl=ttl)
    assert redis_mock.called
    assert res_insert is False
    assert (
        "Cache client error while inserting key test: Mocked exception"
        in caplog.messages
    )


def test_redis_client_delete(redis, flush_cache):
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    # add an entry
    res_insert = redis.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    # delete it
    res_delete = redis.delete(key=cache_key)
    assert res_delete == 1


def test_redis_client_nothing_to_delete(redis, flush_cache):
    cache_key = "testeuuuu"
    res_delete = redis.delete(key=cache_key)
    assert res_delete == 0


def test_redis_client_delete_no_pool(mocker, redis, caplog):
    redis_mock = mocker.patch(
        "redis.commands.core.BasicKeyCommands.delete",
        side_effect=Exception("Mocked exception"),
    )

    cache_key = "testeuuuu"
    res_delete = redis.delete(key=cache_key)
    assert redis_mock.called
    assert res_delete == 0
    assert (
        "Cache client error while deleting key testeuuuu: Mocked exception"
        in caplog.messages
    )


def test_redis_client_get_key_none(redis, flush_cache):
    cache_key = "test"
    data = {"test": "test"}
    ttl = 10

    # add an entry
    res_insert = redis.insert(key=cache_key, data=data, ttl=ttl)
    assert res_insert is True

    res_get = redis.get(key=None)
    assert res_get is None
