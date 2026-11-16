from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import IVectorSearchEngine
from src.soc_agent.schemas import MitreTechnique


@pytest.fixture
def workflow_deps(mocker) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Provide isolated interface-bound mocks for SocAgentWorkflow dependencies."""
    llm_engine: MagicMock = mocker.MagicMock(spec=ILlmEngine)
    embedding_engine: MagicMock = mocker.MagicMock(spec=IEmbeddingEngine)
    vector_engine: MagicMock = mocker.MagicMock(spec=IVectorSearchEngine)
    return llm_engine, embedding_engine, vector_engine


@pytest.fixture
def mitre_technique_factory() -> Callable[[str, float], MitreTechnique]:
    """Factory fixture building valid MitreTechnique domain models for similarity tests."""
    def _create(mitre_id: str, similarity: float) -> MitreTechnique:
        return MitreTechnique(
            mitre_id=mitre_id,
            technic_name=f"Technique {mitre_id}",
            tactics="Execution",
            description="Adversarial behavior description.",
            platforms="windows",
            normalized_similarity=similarity,
        )

    return _create