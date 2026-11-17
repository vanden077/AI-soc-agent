from enum import StrEnum


class EmbeddingProvider(StrEnum):
    """Supported embedding engines."""

    HUGGINGFACE = "huggingface"
    # OPENAI = "openai"  # <= here, any other embedding engine
