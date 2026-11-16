from enum import StrEnum
from typing import Type
from unittest.mock import patch

import pytest

from src.constants import Settings
from src.llm import LlmManager
from src.llm.interfaces.i_llm_engine import ILlmEngine


class _FakeLlmProvider(StrEnum):
    """Isolated test enum decoupling manager tests from real provider names."""

    FAKE_SUPPORTED = "fake_supported"
    FAKE_UNIMPLEMENTED = "fake_unimplemented"


def test_llm_manager_resolves_registered_engine_contract(
    mock_settings: Settings,
    dummy_llm_engine_cls: Type[ILlmEngine],
) -> None:
    """Verify LlmManager dynamically resolves a registered engine and exposes an ILlmEngine contract."""
    fake_dotted_path = "fake.module.DummyLlmEngine"

    with (
        patch("src.llm.llm_manager.LlmProvider", _FakeLlmProvider),
        patch.dict(
            LlmManager._ENGINE_REGISTRY,
            {_FakeLlmProvider.FAKE_SUPPORTED: fake_dotted_path},
            clear=True,
        ),
        patch.object(LlmManager, "_load_engine_class", return_value=dummy_llm_engine_cls) as mock_loader,
    ):
        manager = LlmManager(
            base_url=mock_settings.LLM_URL,
            llm_engine=_FakeLlmProvider.FAKE_SUPPORTED,
            llm_model=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE,
        )

        mock_loader.assert_called_once_with(fake_dotted_path)
        assert isinstance(manager.engine, ILlmEngine)
        assert manager.engine.base_url == mock_settings.LLM_URL
        assert manager.engine.model_name == mock_settings.LLM_MODEL
        assert manager.engine.temperature == mock_settings.LLM_TEMPERATURE


def test_llm_manager_raises_value_error_for_unknown_provider(mock_settings: Settings) -> None:
    """Verify LlmManager raises ValueError when the requested provider string is not supported."""
    invalid_llm_engine = "unknown_engine"

    with pytest.raises(ValueError) as exc_info:
        LlmManager(
            base_url=mock_settings.LLM_URL,
            llm_engine=invalid_llm_engine,
            llm_model=mock_settings.LLM_MODEL,
            temperature=mock_settings.LLM_TEMPERATURE,
        )

    assert f"Engine '{invalid_llm_engine}' not supported" in str(exc_info.value)


def test_llm_manager_raises_not_implemented_error_for_unregistered_enum_value(mock_settings: Settings) -> None:
    """Verify LlmManager raises NotImplementedError when a valid enum entry is missing from _ENGINE_REGISTRY."""
    with (
        patch("src.llm.llm_manager.LlmProvider", _FakeLlmProvider),
        patch.dict(LlmManager._ENGINE_REGISTRY, {}, clear=True),
    ):
        with pytest.raises(NotImplementedError) as exc_info:
            LlmManager(
                base_url=mock_settings.LLM_URL,
                llm_engine=_FakeLlmProvider.FAKE_UNIMPLEMENTED,
                llm_model=mock_settings.LLM_MODEL,
                temperature=mock_settings.LLM_TEMPERATURE,
            )

        assert f"Engine '{_FakeLlmProvider.FAKE_UNIMPLEMENTED}' is listed but not yet implemented." in str(
            exc_info.value
        )


def test_load_engine_class_imports_target_dynamically() -> None:
    """Verify _load_engine_class resolves a class from a standard dotted module path."""
    loaded_cls = LlmManager._load_engine_class("src.llm.interfaces.i_llm_engine.ILlmEngine")
    assert loaded_cls is ILlmEngine
