from typing import Type
from unittest.mock import MagicMock

import pytest

from src.llm.interfaces.i_llm_engine import ILlmEngine, T


class DummyLlmEngine(ILlmEngine[MagicMock]):
    """Backend-agnostic stub implementing ILlmEngine for manager contract testing."""

    def __init__(self, base_url: str, model_name: str, temperature: float = 0.0) -> None:
        self._base_url = base_url
        self._model_name = model_name
        self._temperature = temperature
        self._llm = self._init_llm()

    def _init_llm(self) -> MagicMock:
        return MagicMock()

    def analyze_event(self, prompt: list[tuple[str, str]], response_schema: Type[T]) -> T:
        raise NotImplementedError

    @property
    def engine_name(self) -> str:
        return "Dummy"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature


@pytest.fixture
def dummy_llm_engine_cls() -> Type[DummyLlmEngine]:
    """Expose the backend-agnostic ILlmEngine implementation class."""
    return DummyLlmEngine
