import pytest
from pydantic import BaseModel, ConfigDict


class DummyStructuredOutput(BaseModel):
    """Minimal Pydantic schema used to test structured output without domain coupling."""

    model_config = ConfigDict(extra="forbid")

    is_threat: bool
    summary: str


@pytest.fixture
def sample_prompt() -> list[tuple[str, str]]:
    """Provide a minimal system/user prompt tuple list."""
    return [
        ("system", "You are a SOC triage assistant."),
        ("user", "Suspicious PowerShell execution detected."),
    ]