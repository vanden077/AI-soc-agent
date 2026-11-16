from pathlib import Path
import pytest

from src.constants import Settings


########## ENV VARS ##########
@pytest.fixture(scope="session")
def _session_settings() -> Settings:
    """Instanciate only once per test session"""
    return Settings(
        ENV="development",
        MITRE_STIX_URL="https://fake_mitre_stix_url/enterprise-attack-",
        MITRE_JSON_PATH=Path("fake_mitre_json_path"),
        MITRE_INDEX_SCHEMA_PATH="fake_index_schema_path",
        MITRE_SEMANTIC_HASHES_KEY="mitre:persistence:semantic_hashes",
        MITRE_RELEASE_TAG="19.2",
        PERSISTENCE_ENGINE="redis",
        REDIS_HOST="127.0.0.1",
        REDIS_PORT=6379,
        REDIS_USERNAME="default",
        REDIS_PASSWORD="",
        REDIS_JSON_POOL_SIZE=5,
        REDIS_VECTOR_POOL_SIZE=10,
        REDIS_RETRY_STRATEGY=3,
        REDIS_SSL=False,
        REDIS_VL_INDEX_NAME="mitre_attack_v1",
        REDIS_VL_VECTOR_FIELD="technique_vector",
        REDIS_JSON_POOL_DB_ID=0,
        REDIS_VECTOR_POOL_DB_ID=1,
        EMBEDDING_ENGINE="huggingface",
        EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2",
        EMBEDDING_DIMENSION=384,
        LLM_ENGINE="ollama",
        LLM_MODEL="llama3.1",
        LLM_URL="http://localhost:11434",
        LLM_TEMPERATURE=0.0
    )

@pytest.fixture(scope="function")
def mock_settings(_session_settings: Settings) -> Settings:
    """Return an isolated copy of _session_settings for each tests"""
    return _session_settings.model_copy()
