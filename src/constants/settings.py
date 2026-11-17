from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field


class Settings(BaseModel):
    """Environment vars as constants (from docker compose)"""

    ENV: str = Field(default="development", description="Current environment.")
    MITRE_STIX_URL: str = Field(
        default="https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-",
        description="Download URL to get up to date MITRE STIX.",
    )
    MITRE_JSON_PATH: Path = Field(description="Local path to the MITRE JSON file.")
    MITRE_INDEX_SCHEMA_PATH: str = Field(
        description="Local path to the YAML index schema for RedisVL."
    )
    MITRE_SEMANTIC_HASHES_KEY: str = Field(
        description="Key targeting a simple hash table in persistence storing a unique mitre identifier and its fingerprint hash."
    )
    MITRE_RELEASE_TAG: str = Field(
        default="19.2",
        description="Immutable STIX matrix (v19.2.0) from the official MITRE repository. "
                    "Guarantees idempotency, reproducibility, and guards against upstream breaking changes.",
    )
    PERSISTENCE_ENGINE: str = Field(
        description="Persistence engine to use, ex: redis, qdrant etc..."
    )
    REDIS_HOST: str | None = Field(
        default=None, description="Docker Redis container name/host."
    )
    REDIS_PORT: int | None = Field(default=None, description="Docker Redis port.")
    REDIS_USERNAME: str | None = Field(
        default=None, description="Docker Redis username."
    )
    REDIS_PASSWORD: str | None = Field(
        default=None, description="Docker Redis password."
    )
    REDIS_JSON_POOL_SIZE: int = Field(
        default=5,
        description="Connexion Pool size available for retrieving JSON documents.",
    )
    REDIS_VECTOR_POOL_SIZE: int = Field(
        default=20,
        description="Connexion Pool size available for retrieving vector documents.",
    )
    REDIS_RETRY_STRATEGY: int = Field(
        default=3,
        description="Automatic retries count in case of failure before giving up.",
    )
    REDIS_SSL: bool = Field(default=True, description="Setup SSL for Redis.")
    REDIS_VL_INDEX_NAME: str = Field(
        description="Search index name defined in index_schema.yaml"
    )
    REDIS_VL_VECTOR_FIELD: str = Field(
        description="Vector field name defined in index_schema.yaml"
    )
    REDIS_JSON_POOL_DB_ID: int = Field(
        description="Index of the Redis database storing JSON documents (only because it is a POC, in production everything should be split)."
    )
    REDIS_VECTOR_POOL_DB_ID: int = Field(
        description="Index of the Redis database storing VECTOR documents (only because it is a POC, in production everything should be split)."
    )
    REDIS_QUEUE_PENDING_KEY: str = Field(default="soc:queue:pending", description="Queue pending key name.")
    REDIS_QUEUE_DONE_KEY: str = Field(default="soc:queue:done", description="Queue done key name.")
    REDIS_QUEUE_MAX_PENDING_SIZE: int = Field(default=50, ge=1,
                                              description="Max queue pending size, for throttling/anti DoS.")
    REDIS_QUEUE_MAX_DONE_HISTORY: int = Field(default=100, ge=1,
                                              description="Max queue done history size, to prevent RAM explosion on small systems.")
    REDIS_JOBS_TTL: int = Field(default=3600, description="Global TTL for Redis retention in seconds.")
    WORKER_POLL_INTERVAL: float = Field(default=0.5,
                                        description="Poll interval in seconds for worker polling jobs from Redis.")
    EMBEDDING_ENGINE: str = Field(
        description="Embedding engine to use, ex: huggingface, openai etc..."
    )
    EMBEDDING_MODEL_NAME: str = Field(
        description="Embedding model to use, ex: all-MiniLM-L6-v2, all-mpnet-base-v2 etc..."
    )
    EMBEDDING_DIMENSION: int = Field(
        description="Strict geometric vector dimension required by the EMBEDDING_MODEL_NAME (e.g., 384 for all-MiniLM-L6-v2, 768, 1536). Must match the active Redis index configuration."
    )
    LLM_ENGINE: str = Field(description="LLM engine to use, ex: ollama, Mistral etc...")
    LLM_MODEL: str = Field(
        description="LLM model tu use, ex: llama3.1, mistral7b etc..."
    )
    LLM_URL: str = Field(description="URL of the LLM engine to use.")
    LLM_TEMPERATURE: float = Field(
        description="Indication for the degree of freedom of the model."
    )

    @computed_field
    @property
    def MITRE_FULL_STIX_URL(self) -> str:
        return f"{self.MITRE_STIX_URL}{self.MITRE_RELEASE_TAG}.json"

    model_config = ConfigDict(extra="ignore", frozen=True)
