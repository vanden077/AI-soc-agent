from types import SimpleNamespace

import pytest
from src.embedding.embedding_manager import EmbeddingManager
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
from src.embedding.providers.embedding_provider import EmbeddingProvider

from tests.embedding.conftest import DummyEmbeddingEngine


def test_init_resolves_registered_provider_and_exposes_engine(
    mocker,
    dummy_embedding_engine_cls: type[DummyEmbeddingEngine],
) -> None:
    """Nominal: resolves a valid provider from _ENGINE_REGISTRY and instantiates its engine."""
    mocker.patch.dict(
        EmbeddingManager._ENGINE_REGISTRY,
        {EmbeddingProvider.HUGGINGFACE: "fake.module.DummyEmbeddingEngine"},
        clear=True,
    )
    mocker.patch(
        "src.embedding.embedding_manager.importlib.import_module",
        return_value=SimpleNamespace(DummyEmbeddingEngine=dummy_embedding_engine_cls),
    )

    manager = EmbeddingManager(
        provider=EmbeddingProvider.HUGGINGFACE.value,
        model_name="BAAI/bge-small-en-v1.5",
    )

    assert isinstance(manager.engine, IEmbeddingEngine)
    assert isinstance(manager.engine, dummy_embedding_engine_cls)
    assert manager.engine.model_name == "BAAI/bge-small-en-v1.5"
    assert manager.engine.engine_name == "Dummy"


def test_init_raises_value_error_on_unsupported_provider() -> None:
    """Error: unknown provider string raises ValueError listing available engines."""
    with pytest.raises(ValueError, match="Engine 'unknown_provider' not supported"):
        EmbeddingManager(
            provider="unknown_provider",
            model_name="BAAI/bge-small-en-v1.5",
        )


def test_init_raises_not_implemented_error_when_provider_unregistered(mocker) -> None:
    """Error: valid enum member missing from _ENGINE_REGISTRY raises NotImplementedError."""
    mocker.patch.dict(EmbeddingManager._ENGINE_REGISTRY, {}, clear=True)

    with pytest.raises(
        NotImplementedError,
        match="is listed but not yet implemented",
    ):
        EmbeddingManager(
            provider=EmbeddingProvider.HUGGINGFACE.value,
            model_name="BAAI/bge-small-en-v1.5",
        )
