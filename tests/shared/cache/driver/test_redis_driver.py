from fakeredis import FakeRedis

from src.shared.cache import RedisClient


def test_driver_instance():
    cache_client = RedisClient(
        host="test",
        port=1,
        username="username",
        password="test",
        max_size_pool=1,
        retry_strategy=1,
    )

    assert cache_client is not None
    assert cache_client.host == "test"
    assert cache_client.port == 1
    assert cache_client.retry_strategy == 1
    assert cache_client.pool_size == 0  # because pool is not ready


def test_driver_pool(redis, flush_cache):
    assert redis.pool_size == 2147483648  # because of fakeredis
    assert redis.retry_strategy == 3
    assert isinstance(redis.redis_client, FakeRedis)


def test_driver_pool_exception(mocker, caplog):
    mocker.patch(
        "redis.commands.core.ManagementCommands.ping",
        side_effect=Exception("Mocked exception"),
    )

    cache_client = RedisClient(
        host="test",
        port=1,
        username="username",
        password="test",
        max_size_pool=1,
        retry_strategy=1,
    )
    cache_client.init_pool()

    assert cache_client.redis_client is None
    assert "Cache pool is KO because: Mocked exception" in caplog.messages


def test_health_check_server_up(redis):
    assert redis.health() is True


def test_health_check_exception(mocker, redis, caplog):
    mocker.patch(
        "redis.commands.core.ManagementCommands.ping",
        side_effect=Exception("Mocked exception"),
    )

    try:
        redis.health()
    except Exception as err:  # noqa: BLE001
        assert str(err) == "Cache error"

    assert (
        "Error something went wrong, cant ping Cache server: Mocked exception"
        in caplog.messages
    )


def test_pool_is_recreated_if_connection_lost(redis):
    ret = redis.insert(key=1, data={"test": "test"}, ttl=10)
    assert ret is True
    # destroy pool
    redis._client = None
    # assert is connection is lost
    assert redis.pool_size == 0
    # get data inserted before, this asserts that pool has been re-created
    ret = redis.get(key=1)
    assert redis.pool_size == 2147483648  # because of fakeredis
    assert ret == {"test": "test"}


def test_list_keys(redis, flush_cache, mocker):
    key = "test_key_"

    # insert 10 keys in redis
    for i in range(10):
        tmp_key = key + str(i)
        ret = redis.insert(key=tmp_key, data={"test": "test"}, ttl=10)
        assert ret is True

    # list all keys without matching pattern
    result_size, result = redis.list_keys()
    assert result_size == 10

    # assert all keys are returned
    for i in range(10):
        assert result[i] == key + str(i)

    # insert 10 more keys to test pattern matching
    pattern_key = "pattern_key_"
    for i in range(10):
        tmp_pattern_key = pattern_key + str(i)
        ret = redis.insert(key=tmp_pattern_key, data={"test": "test"}, ttl=10)
        assert ret is True

    # list only keys previously inserted
    result_size, result = redis.list_keys(match="pattern_key_*")
    assert result_size == 10

    # assert only keys starting by pattern_key_ are returned
    for i in range(10):
        assert result[i] == pattern_key + str(i)

    # test batch recovery
    result_size, result = redis.list_keys(batch_size=2)
    assert result_size == 20  # because there are test_key_ and pattern_key_

    # assert other key types are converted to str
    mocker.patch("redis.commands.core.ScanCommands.scan", return_value=(0, [1, 2]))
    _, result = redis.list_keys()
    for key in result:
        assert isinstance(key, str)


def test_list_keys_exception(mocker, redis, caplog):
    mocker.patch(
        "redis.commands.core.ScanCommands.scan",
        side_effect=Exception("Mocked exception"),
    )

    key = "test_key_"
    # insert 10 keys in redis
    for i in range(10):
        tmp_key = key + str(i)
        ret = redis.insert(key=tmp_key, data={"test": "test"}, ttl=10)
        assert ret is True

    # get previously inserted keys
    result_size, result = redis.list_keys()
    assert result_size == 0
    assert result == []
    assert "Cache client error while listing keys: Mocked exception" in caplog.messages
