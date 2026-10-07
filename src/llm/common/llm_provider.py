from enum import StrEnum


class LlmProvider(StrEnum):
    """Supported llm engines."""
    OLLAMA = "ollama"
    # Mistral = "mistral"  # <= here, any other llm engine