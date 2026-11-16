from enum import StrEnum


class PersistenceProvider(StrEnum):
    """Supported persistence engine backends."""

    REDIS = "redis"