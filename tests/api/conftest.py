from collections.abc import Generator
from types import SimpleNamespace
from typing import Callable
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.schemas import (
    AnalysisJobRecord,
    AvailablePlatforms,
    JobStatus,
    LogIngressPayload
)
from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.main import app
from src.persistence.interfaces import (
    IJsonStorageEngine,
    IQueueEngine,
    IVectorSearchEngine,
)


@pytest.fixture(scope="function")
def mock_embedding_engine(mocker) -> MagicMock:
    """Isolated interface-bound mock for IEmbeddingEngine."""
    return mocker.MagicMock(spec=IEmbeddingEngine)


@pytest.fixture(scope="function")
def mock_llm_engine(mocker) -> MagicMock:
    """Isolated interface-bound mock for ILlmEngine."""
    return mocker.MagicMock(spec=ILlmEngine)


@pytest.fixture(scope="function")
def mock_json_cache(mocker) -> MagicMock:
    """Isolated interface-bound mock for IJsonStorageEngine."""
    return mocker.MagicMock(spec=IJsonStorageEngine)


@pytest.fixture(scope="function")
def mock_vector_cache(mocker) -> MagicMock:
    """Isolated interface-bound mock for IVectorSearchEngine."""
    return mocker.MagicMock(spec=IVectorSearchEngine)


@pytest.fixture(scope="function")
def mock_queue_cache(mocker) -> MagicMock:
    """Isolated interface-bound mock for IVectorSearchEngine."""
    return mocker.MagicMock(spec=IQueueEngine)


@pytest.fixture
def sample_job_record_factory() -> Callable[..., AnalysisJobRecord]:
    """Factory fixture building valid AnalysisJobRecord instances for API and service tests."""

    def _create(
            job_id: str = "11111111-1111-1111-1111-111111111111",
            job_status: JobStatus = JobStatus.COMPLETED,
    ) -> AnalysisJobRecord:
        return AnalysisJobRecord(
            job_id=job_id,
            status=job_status,
            log_ingress_payload=LogIngressPayload(
                platform=AvailablePlatforms.WINDOWS,
                raw_log="EventID=4688 New Process Created",
            ),
        )

    return _create


@pytest.fixture(scope="function")
def lifespan_mocks(
        mocker,
        mock_settings: Settings,
        mock_embedding_engine: MagicMock,
        mock_llm_engine: MagicMock,
        mock_json_cache: MagicMock,
        mock_vector_cache: MagicMock,
        mock_queue_cache: MagicMock,
) -> SimpleNamespace:
    """Centralized startup boundary mocks for lifespan tests."""
    return SimpleNamespace(
        load_env_vars=mocker.patch("src.main.load_env_vars", return_value=mock_settings),
        configure_dev_helpers=mocker.patch("src.main.configure_dev_helpers"),
        download_stix_file=mocker.patch("src.main.download_stix_file"),
        init_embedding_engine=mocker.patch("src.main.init_embedding_engine", return_value=mock_embedding_engine),
        run_pipeline=mocker.patch("src.main.run_pipeline"),
        init_json_pool=mocker.patch("src.main.init_json_pool", return_value=mock_json_cache),
        init_vector_pool=mocker.patch("src.main.init_vector_pool", return_value=mock_vector_cache),
        init_queue_pool=mocker.patch("src.main.init_queue_pool", return_value=mock_queue_cache),
        init_llm=mocker.patch("src.main.init_llm", return_value=mock_llm_engine),
    )


@pytest.fixture(scope="function")
def mock_client(mocker, lifespan_mocks: SimpleNamespace) -> Generator[TestClient]:
    """
    Isolated HTTP TestClient executing FastAPI lifespan with mocked startup boundaries.
    """
    mocker.stop(lifespan_mocks.configure_dev_helpers)
    with TestClient(app, follow_redirects=False) as client:
        yield client
