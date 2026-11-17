from unittest.mock import MagicMock, patch

import pytest
import redis.exceptions


def test_driver_instance(redis_driver_factory):
    """Test inherited instance."""
    driver = redis_driver_factory()
    assert driver is not None
    assert driver.host == "test"
    assert driver.port == 1
    assert driver.retry_strategy == 1
    assert driver.pool_size == 0  # because pool is not ready
    assert driver.decode_responses == True


def test_driver_pool(redis_driver_factory):
    """Test connexion pool availability."""
    driver = redis_driver_factory()
    driver.init_pool()
    assert driver.pool_size == 1  # now pool is ready with 1 connexion


def test_driver_pool_exception(mock_redis_driver, redis_driver_factory):
    """Make Redis crash when init connexion pool."""
    mock_redis_driver.side_effect = redis.exceptions.ConnectionError(
        "SSL handshake failed."
    )
    driver = redis_driver_factory()

    with pytest.raises(redis.exceptions.ConnectionError, match="SSL handshake failed."):
        driver.init_pool()


def test_getting_client_raise_if_no_pool(redis_driver_factory):
    """Test getting Redis client connexion pool raise exception if pool is not initialized"""
    driver = redis_driver_factory()

    with pytest.raises(
            RuntimeError,
            match="Critical: pool connexion is not initialized, "
                  "please call init_pool before performing Redis operations.",
    ):
        _ = driver.redis_client


def test_init_pool_preserves_same_client_instance(
        mock_redis_driver, redis_driver_factory
):
    """Should preserve the exact same internal client instance if init_pool is called multiple times."""
    driver = redis_driver_factory()

    # 1. First initialization: Redis constructor is called
    driver.init_pool()
    # We grab the memory identity of the client object created by our mock factory
    first_client_id = id(mock_redis_driver.return_value)
    # 2. Second execution (the guarded clause should trigger here)
    driver.init_pool()

    # We check if a new call was recorded. call_count must remain at 1
    assert mock_redis_driver.call_count == 1
    # The return_value in memory is still the first one, proving no second instance was forged
    assert id(mock_redis_driver.return_value) == first_client_id


def test_close_disables_cache_operations(redis_driver_factory):
    """Should successfully close the pool and release underlying resources."""
    driver = redis_driver_factory()
    driver.init_pool()
    driver.close()

    # Check the connection pool state
    assert (
            driver.redis_client.connection_pool.pid is not None
    )  # Pool is still bound to the PID
    # Check that no active connections are remaining
    assert len(driver.redis_client.connection_pool._available_connections) == 0


def test_health_check_server_up(redis_driver_factory):
    """Test ping command is correctly cast, Redis return an integer not a boolean"""
    driver = redis_driver_factory()
    driver.init_pool()
    assert driver.health() is True


def test_health_check_exception(redis_driver_factory, caplog):
    """Make ping command crash"""
    driver = redis_driver_factory()
    driver.init_pool()

    mock_client = MagicMock()
    mock_client.ping.side_effect = ConnectionError(
        "Redis AUTH failed or Network timeout."
    )
    driver._client = mock_client

    assert driver.health() is False
    assert (
            "Error something went wrong, cant ping Cache server: Redis AUTH failed or Network timeout."
            in caplog.messages
    )


def test_list_keys(redis_driver_factory):
    """Test listing keys"""
    driver = redis_driver_factory()
    driver.init_pool()

    try:
        key = "test_key_"
        data = "test"

        # insert 10 keys in redis
        for i in range(10):
            tmp_key = key + str(i)
            driver.redis_client.set(name=tmp_key, value=data, ex=1)

        # list all keys without matching pattern
        result_size, result = driver.list_keys()
        assert result_size == 10

        # assert all keys are returned
        for i in range(10):
            assert result[i] == key + str(i)
    finally:
        driver.flush_db()


def test_list_keys_pattern_matching(redis_driver_factory):
    """Test listing keys with filter"""
    driver = redis_driver_factory()
    driver.init_pool()

    try:
        key = "test_key_"
        pattern_key = "pattern_key_"
        data = "test"

        # insert 10 keys in redis
        for i in range(10):
            tmp_key = key + str(i)
            driver.redis_client.set(name=tmp_key, value=data, ex=1)

        # insert 10 more keys to test pattern matching
        for i in range(10):
            tmp_pattern_key = pattern_key + str(i)
            driver.redis_client.set(name=tmp_pattern_key, value=data, ex=1)

        # check there is exactly 20 keys
        result_size, result = driver.list_keys()
        assert result_size == 20

        # list only keys starting by "test_key_"
        result_size, result = driver.list_keys(match="test_key_*")
        assert result_size == 10

        # assert only keys starting by "test_key_" are returned
        for i in range(10):
            assert result[i] == key + str(i)

        # list only keys starting by "pattern_key_"
        result_size, result = driver.list_keys(match="pattern_key_*")
        assert result_size == 10

        # assert only keys starting by "pattern_key_" are returned
        for i in range(10):
            assert result[i] == pattern_key + str(i)

        # test batch recovery
        result_size, _ = driver.list_keys(batch_size=2)
        assert result_size == 20
    finally:
        driver.flush_db()


@pytest.mark.parametrize("keys", [(0, [b"1", b"2"]), (0, [1, 2]), (0, [True, False])])
def test_list_keys_are_cast_in_str(redis_driver_factory, mocker, keys):
    """Test keys that are not Strings are cast to str before returning response"""
    mocker.patch("redis.commands.core.ScanCommands.scan", return_value=keys)
    driver = redis_driver_factory()
    driver.init_pool()
    _, result = driver.list_keys()

    for key in result:
        assert isinstance(key, str)


def test_list_keys_exception(redis_driver_factory, mocker, caplog):
    """Make scan command crash during key listing"""
    mocker.patch(
        "redis.commands.core.ScanCommands.scan",
        side_effect=Exception("Mocked exception"),
    )
    driver = redis_driver_factory()
    driver.init_pool()
    result_size, result = driver.list_keys()

    assert result_size == 0
    assert result == []
    # exception is caught into the function, and return an empty list.
    # Here we want to be sure that the non-existence of keys is logged.
    assert "Cache client error while listing keys: Mocked exception" in caplog.messages


####### SPECIFIC PART FOR VECTORS #######
def test_init_search_index_lifecycle_success(
        redis_driver_factory, mock_redis_vl_search_index
):
    """Should successfully bind a valid SearchIndex instance to the driver."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()
    driver.init_search_index("mitre_attack_v1")
    assert driver.search_index is mock_redis_vl_search_index


def test_init_search_index_with_non_vector_client_raises(redis_driver_factory):
    """Should strictly raise a RuntimeError while initializing SearchIndex with non-vector client."""
    driver = redis_driver_factory(decode_responses=False)
    driver.init_pool()

    with pytest.raises(
            RuntimeError,
            match="Critical: This persistence client instance was initialized without vector capabilities.",
    ):
        driver.init_search_index("mitre_attack_v1")


@pytest.mark.parametrize(
    "schema_path",
    [
        None,
        " ",
        "",
    ],
)
def test_init_search_index_raises_value_error_on_none(
        redis_driver_factory, schema_path
):
    """Should strictly raise a ValueError if the injected search index is None or empty."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()

    with pytest.raises(
            ValueError,
            match="Critical: path to RediVL index schema cannot be None or empty.",
    ):
        driver.init_search_index(schema_path)


def test_init_search_index_skips_creation_when_already_exists(
        redis_driver_factory, mock_redis_vl_search_index
):
    """Should bind existing SearchIndex without calling create() when index already exists."""
    mock_redis_vl_search_index.exists.return_value = True
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()

    driver.init_search_index("mitre_attack_v1")

    mock_redis_vl_search_index.create.assert_not_called()
    assert driver.search_index is mock_redis_vl_search_index


@pytest.mark.parametrize(
    "exceptions",
    [
        ValueError,
        TypeError,
        RuntimeError,
    ],
)
def test_init_search_index_crash_on_creating_schema_from_yaml(
        redis_driver_factory, exceptions, caplog
):
    """Should raise ValueError, TypeError, or RuntimeError if SearchIndex.from_yaml crashes."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()

    with patch(
            "src.persistence.engine.redis.driver.redis_driver.SearchIndex"
    ) as mock_search_index_cls:
        mock_search_index_cls.from_yaml.side_effect = exceptions(
            "error message from RedisVL"
        )

        with pytest.raises(exceptions):
            driver.init_search_index("mitre_attack_v1")
        assert (
                "Error while creating search index from mitre_attack_v1: error message from RedisVL"
                in caplog.messages
        )


def test_get_index_metadata_fields_extraction_success(
        redis_driver_factory, mock_redis_vl_search_index
):
    """Should correctly extract non-vector metadata return fields from the index schema."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()
    driver.init_search_index("mitre_attack_v1")

    extracted_fields = driver.get_index_metadata_fields()

    assert isinstance(extracted_fields, set)
    assert extracted_fields == {"id", "raw_content"}


def test_get_index_metadata_fields_raise_because_invalid_client(redis_driver_factory):
    """Test getting index metadata fields raises error because the instance has no vector capabilities."""
    driver = redis_driver_factory(decode_responses=False)
    driver.init_pool()

    with pytest.raises(
            RuntimeError,
            match="This persistence client instance was initialized without vector capabilities.",
    ):
        driver.get_index_metadata_fields()


def test_get_index_metadata_fields_raise_because_not_loaded(redis_driver_factory):
    """Test getting index metadata fields raises error because the search index is not loaded yet."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()

    with pytest.raises(
            RuntimeError, match="Search index has not been loaded into the driver yet."
    ):
        driver.get_index_metadata_fields()


def test_get_index_vector_fields_catalog_success(
        redis_driver_factory, mock_redis_vl_search_index
):
    """
    Normal process, everything is ok, function should return a dict of VectorFieldSpecs.
    """
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()
    driver.init_search_index("mitre_attack_v1")

    vectors_catalog = driver.get_index_vector_fields_catalog()

    assert isinstance(vectors_catalog, dict)
    assert len(vectors_catalog) == 2

    assert "text_embedding" in vectors_catalog
    text_spec = vectors_catalog["text_embedding"]
    assert text_spec.name == "text_embedding"
    assert text_spec.dimension == 384
    assert text_spec.metric == "cosine"
    assert text_spec.algorithm == "hnsw"
    assert text_spec.source_path == "$.payload.text_embedding"

    assert "image_embedding" in vectors_catalog
    image_spec = vectors_catalog["image_embedding"]
    assert image_spec.name == "image_embedding"
    assert image_spec.dimension == 384
    assert image_spec.metric == "l2"
    assert image_spec.algorithm == "flat"
    assert image_spec.source_path == "$.payload.image_embedding"


def test_get_index_vector_fields_catalog_fallback_source_path(
        redis_driver_factory, mock_redis_vl_search_index
):
    """Should fall back to field_name as source_path when explicit path is omitted in schema."""
    mock_redis_vl_search_index.schema.model_dump.return_value = {
        "fields": {
            "embedding": {
                "type": "vector",
                "attrs": {
                    "dims": 384,
                    "distance_metric": "cosine",
                    "algorithm": "hnsw",
                },
            }
        }
    }
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()
    driver.init_search_index("mitre_attack_v1")

    vectors_catalog = driver.get_index_vector_fields_catalog()

    assert vectors_catalog["embedding"].source_path == "embedding"


def test_get_index_vector_fields_catalog_fail_no_vectors(
        redis_driver_factory, mock_redis_vl_search_index
):
    """
    Check driver raises exception if schema does not contain any vectors.
    """
    mock_redis_vl_search_index.schema.model_dump.return_value = {
        "fields": {
            "id": {"type": "tag"},
            "raw_content": {"type": "text"},
        }
    }

    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()
    driver.init_search_index("mitre_attack_v1")

    with pytest.raises(
            ValueError,
            match="Invalid index configuration: No explicit vector field detected. "
                  "Please check the index YAML file; it must contain at least one vector field.",
    ):
        driver.get_index_vector_fields_catalog()


@pytest.mark.parametrize(
    "yaml_prefix, expected_clean_prefix",
    [
        ("mitre:", "mitre:"),
        ("mitre", "mitre:"),
    ],
)
def test_get_index_prefix_formatting(
        redis_driver_factory,
        mock_redis_vl_search_index,
        yaml_prefix,
        expected_clean_prefix,
):
    """Should guarantee that the returned index prefix always terminates with a structural colon."""
    driver = redis_driver_factory(decode_responses=False, vector_capability=True)
    driver.init_pool()

    mock_redis_vl_search_index.schema.index.prefix = yaml_prefix
    driver.init_search_index("mitre_attack_v1")

    formatted_prefix = driver.get_index_prefix()

    assert formatted_prefix == expected_clean_prefix
