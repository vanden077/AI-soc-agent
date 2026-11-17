from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from src.persistence.interfaces.i_json_storage_engine import IJsonStorageEngine
from src.persistence.interfaces.i_persistence_factory import IPersistenceFactory
from src.persistence.interfaces.i_queue_engine import IQueueEngine
from src.persistence.interfaces.i_vector_ingestion_engine import IVectorIngestionEngine
from src.persistence.interfaces.i_vector_search_engine import IVectorSearchEngine
from src.persistence.persistence_manager import PersistenceManager
from src.persistence.providers.persistence_provider import PersistenceProvider


@pytest.fixture
def mock_factory(mocker) -> MagicMock:
    """Agnostic mock factory implementing IPersistenceFactory."""
    factory_instance = mocker.MagicMock(spec=IPersistenceFactory)
    factory_cls = mocker.MagicMock(return_value=factory_instance)

    mocker.patch.dict(
        PersistenceManager._FACTORY_REGISTRY,
        {PersistenceProvider.REDIS: "fake.module.FakePersistenceFactory"},
        clear=True,
    )
    mocker.patch(
        "src.persistence.persistence_manager.importlib.import_module",
        return_value=SimpleNamespace(FakePersistenceFactory=factory_cls),
    )
    return factory_instance


def test_init_resolves_registered_provider_and_instantiates_factory(
        mock_factory: MagicMock,
) -> None:
    """Nominal: resolves a valid provider from _FACTORY_REGISTRY via importlib."""
    manager = PersistenceManager(provider=PersistenceProvider.REDIS.value)

    assert manager._factory is mock_factory


def test_init_raises_value_error_on_unsupported_provider() -> None:
    """Error: unknown provider string raises ValueError listing available providers."""
    with pytest.raises(
            ValueError, match="Persistence provider 'unknown_db' not supported"
    ):
        PersistenceManager(provider="unknown_db")


def test_init_raises_not_implemented_error_when_provider_unregistered(mocker) -> None:
    """Error: valid enum member missing from _FACTORY_REGISTRY raises NotImplementedError."""
    mocker.patch.dict(PersistenceManager._FACTORY_REGISTRY, {}, clear=True)

    with pytest.raises(
            NotImplementedError,
            match="is listed but not yet implemented",
    ):
        PersistenceManager(provider=PersistenceProvider.REDIS.value)


def test_create_json_engine_delegates_to_factory(
        mock_factory: MagicMock,
        mocker,
) -> None:
    """Delegation: forwards connection kwargs to factory.create_json_engine."""
    expected_engine = mocker.MagicMock(spec=IJsonStorageEngine)
    mock_factory.create_json_engine.return_value = expected_engine
    manager = PersistenceManager(provider=PersistenceProvider.REDIS.value)

    result = manager.create_json_engine(host="db.internal", port=6379, db=0)

    mock_factory.create_json_engine.assert_called_once_with(
        host="db.internal", port=6379, db=0
    )
    assert result is expected_engine


def test_create_vector_search_engine_delegates_to_factory(
        mock_factory: MagicMock,
        mocker,
) -> None:
    """Delegation: forwards index_path and connection kwargs to factory.create_vector_search_engine."""
    expected_engine = mocker.MagicMock(spec=IVectorSearchEngine)
    mock_factory.create_vector_search_engine.return_value = expected_engine
    manager = PersistenceManager(provider=PersistenceProvider.REDIS.value)

    result = manager.create_vector_search_engine(
        index_path="/schemas/index.yaml",
        host="db.internal",
        db=1,
    )

    mock_factory.create_vector_search_engine.assert_called_once_with(
        index_path="/schemas/index.yaml",
        host="db.internal",
        db=1,
    )
    assert result is expected_engine


def test_create_vector_ingestion_engine_delegates_to_factory(
        mock_factory: MagicMock,
        mocker,
) -> None:
    """Delegation: forwards ingestion arguments and connection kwargs to factory.create_vector_ingestion_engine."""
    expected_engine = mocker.MagicMock(spec=IVectorIngestionEngine)
    mock_factory.create_vector_ingestion_engine.return_value = expected_engine
    manager = PersistenceManager(provider=PersistenceProvider.REDIS.value)

    result = manager.create_vector_ingestion_engine(
        index_path="/schemas/index.yaml",
        target_vector_field="text_embedding",
        semantic_hashes_key="catalog:hashes",
        host="db.internal",
        db=1,
    )

    mock_factory.create_vector_ingestion_engine.assert_called_once_with(
        index_path="/schemas/index.yaml",
        target_vector_field="text_embedding",
        semantic_hashes_key="catalog:hashes",
        host="db.internal",
        db=1,
    )
    assert result is expected_engine


def test_create_queue_engine_delegates_to_factory(
        mock_factory: MagicMock,
        mocker,
) -> None:
    """Delegation: forwards queue arguments and connection kwargs to factory.create_queue_engine."""
    expected_engine = mocker.MagicMock(spec=IQueueEngine)
    mock_factory.create_queue_engine.return_value = expected_engine
    manager = PersistenceManager(provider=PersistenceProvider.REDIS.value)

    result = manager.create_queue_engine(
        pending_key="soc:queue:pending",
        done_key="soc:queue:done",
        max_done_history=50,
        host="db.internal",
        db=0,
    )

    mock_factory.create_queue_engine.assert_called_once_with(
        pending_key="soc:queue:pending",
        done_key="soc:queue:done",
        max_done_history=50,
        host="db.internal",
        db=0,
    )
    assert result is expected_engine
