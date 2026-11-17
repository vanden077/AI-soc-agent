from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.dataset_test import STIX_MOCK


def _stub_embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Generates a memory-contiguous mock float array for each text payload chunk.
    """
    return [[0.11] * 384 for _ in texts]


@pytest.fixture
def mock_file_context() -> MagicMock:
    """
    Simulates filesystem state boundaries for the target STIX bundle path.
    Defaults to an existing file layout.
    """
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "enterprise-attack-mock.json"
    return mock_path


@pytest.fixture
def mock_infra() -> dict[str, MagicMock]:
    """
    Provides raw binary behavioral toggles for outer infrastructure boundaries.
    Defaults to nominal state ('on' / functioning).
    """
    mock_redis = MagicMock()
    mock_embedding = MagicMock()

    # Nominal defaults
    mock_redis.fetch_remote_hashes.return_value = {}
    mock_redis.execute_bulk_upsert.return_value = None
    mock_redis.set_remote_hashes.return_value = None

    # Adhering to strict readability rules: using the named stub function
    mock_embedding.embed_documents.side_effect = _stub_embed_documents

    return {"redis": mock_redis, "embedding": mock_embedding}


@pytest.fixture
def stix_mock_stream():
    """
    Intercepts and routes ijson stream tokens directly into the immutable STIX_MOCK dictionary matrix array.
    """
    with patch("src.data_pipeline.pipelines.stix_pipeline.ijson.items") as mock_ijson:
        mock_ijson.return_value = iter(STIX_MOCK["objects"])
        yield mock_ijson
