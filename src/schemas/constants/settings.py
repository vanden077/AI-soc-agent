from pathlib import Path
from pydantic import Field, BaseModel, ConfigDict


class Settings(BaseModel):
    """Environment vars as constants (from docker compose)"""
    ENV: str = Field(
        default="development",
        validation_alias="ENV",
        description="Current environment."
    )
    MITRE_STIX_URL: str = Field(
        validation_alias="MITRE_STIX_URL",
        description="Download URL to get up to date MITRE STIX."
    )
    MITRE_JSON_PATH: Path = Field(
        validation_alias="MITRE_JSON_PATH",
        description="Local path to the MITRE JSON file.")
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
    INDEX_NAME: str = Field(
        validation_alias="INDEX_NAME",
        description="Index name of the vectorized MITRE in Redis."
    )

    model_config = ConfigDict(extra="ignore", frozen=True)
