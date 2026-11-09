from pathlib import Path
from pydantic import Field, BaseModel, ConfigDict, computed_field


class Settings(BaseModel):
    """Environment vars as constants (from docker compose)"""
    ENV: str = Field(
        default="development",
        validation_alias="ENV",
        description="Current environment."
    )
    MITRE_STIX_URL: str = Field(
        default="https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-",
        validation_alias="MITRE_STIX_URL",
        description="Download URL to get up to date MITRE STIX."
    )
    MITRE_JSON_PATH: Path = Field(
        validation_alias="MITRE_JSON_PATH",
        description="Local path to the MITRE JSON file.")
    MITRE_INDEX_SCHEMA_PATH: str = Field(
        validation_alias="MITRE_INDEX_SCHEMA_PATH",
        description="Local path to the YAML index schema for RedisVL.")
    MITRE_SEMANTIC_HASHES_KEY: str = Field(
        validation_alias="MITRE_SEMANTIC_HASHES_KEY",
        description="Key targeting a simple hash table in cache storing "
                    "a unique mitre identifier and its fingerprint hash.")
    MITRE_RELEASE_TAG: str = Field(
        default="19.2",
        validation_alias="MITRE_RELEASE_TAG",
        description="Immutable STIX matrix (v19.2.0) from the official MITRE repository. "
                    "Guarantees idempotency, reproducibility, and guards against upstream breaking changes.")
    REDIS_HOST: str | None = Field(
        default=None,
        validation_alias="REDIS_HOST",
        description="Docker Redis container name/host."
    )
    REDIS_PORT: int | None = Field(
        default=None,
        validation_alias="REDIS_PORT",
        description="Docker Redis port."
    )
    REDIS_USERNAME: str | None = Field(
        default=None,
        validation_alias="REDIS_USERNAME",
        description="Docker Redis username."
    )
    REDIS_PASSWORD: str | None = Field(
        default=None,
        validation_alias="REDIS_PASSWORD",
        description="Docker Redis password."
    )
    REDIS_JSON_POOL_SIZE: int = Field(
        default=5,
        validation_alias="REDIS_JSON_POOL_SIZE",
        description="Connexion Pool size available for retrieving JSON documents."
    )
    REDIS_VECTOR_POOL_SIZE: int = Field(
        default=20,
        validation_alias="REDIS_VECTOR_POOL_SIZE",
        description="Connexion Pool size available for retrieving vector documents."
    )
    REDIS_RETRY_STRATEGY: int = Field(
        default=3,
        validation_alias="REDIS_RETRY_STRATEGY",
        description="Automatic retries count in case of failure before giving up."
    )
    REDIS_SSL: bool = Field(
        default=True,
        validation_alias="REDIS_SSL",
        description="Setup SSL for Redis."
    )
    REDIS_VL_INDEX_NAME: str = Field(
        validation_alias="REDIS_VL_INDEX_NAME",
        description="Search index name defined in index_schema.yaml"
    )
    REDIS_VL_VECTOR_FIELD: str = Field(
        validation_alias="REDIS_VL_VECTOR_FIELD",
        description="Vector field name defined in index_schema.yaml"
    )
    REDIS_JSON_POOL_DB_ID: int = Field(
        validation_alias="REDIS_JSON_POOL_DB_ID",
        description="Index of the Redis database storing JSON documents "
                    "(only because it is a POC, in production everything should be split).")
    REDIS_VECTOR_POOL_DB_ID: int = Field(
        validation_alias="REDIS_VECTOR_POOL_DB_ID",
        description="Index of the Redis database storing VECTOR documents "
                    "(only because it is a POC, in production everything should be split).")
    EMBEDDING_ENGINE: str = Field(
        validation_alias="EMBEDDING_ENGINE",
        description="Embedding engine to use, ex: huggingface, openai etc..."
    )
    EMBEDDING_MODEL_NAME: str = Field(
        validation_alias="EMBEDDING_MODEL_NAME",
        description="Embedding model to use, ex: all-MiniLM-L6-v2, all-mpnet-base-v2 etc..."
    )
    EMBEDDING_DIMENSION: int = Field(
        validation_alias="EMBEDDING_DIMENSION",
        description="Strict geometric vector dimension required by the EMBEDDING_MODEL_NAME (e.g., 384 for all-MiniLM-L6-v2, 768, 1536). Must match the active Redis index configuration."
    )
    LLM_ENGINE: str = Field(
        validation_alias="LLM_ENGINE",
        description="LLM engine to use, ex: ollama, Mistral etc..."
    )
    LLM_MODEL: str = Field(
        validation_alias="LLM_MODEL",
        description="LLM model tu use, ex: llama3.1, mistral7b etc..."
    )
    LLM_URL: str = Field(
        validation_alias="LLM_URL",
        description="URL of the LLM engine to use."
    )
    LLM_TEMPERATURE: float = Field(
        validation_alias="LLM_TEMPERATURE",
        description="Indication for the degree of freedom of the model."
    )

    @computed_field
    @property
    def MITRE_FULL_STIX_URL(self) -> str:
        return f"{self.MITRE_STIX_URL}{self.MITRE_RELEASE_TAG}.json"

    model_config = ConfigDict(extra="ignore", frozen=True)
