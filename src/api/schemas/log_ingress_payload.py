from enum import StrEnum
from pydantic import BaseModel, Field, field_validator


class AvailablePlatforms(StrEnum):
    """Official MITRE ATT&CK Enterprise platforms ecosystem matrix mapping."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    PRE = "pre"
    OFFICE_SUITE = "office suite"
    IDENTITY_PROVIDER = "identity provider"
    SAAS = "saas"
    IAAS = "iaas"
    NETWORK_DEVICES = "network devices"
    CONTAINERS = "containers"
    ESXI = "esxi"

class LogIngressPayload(BaseModel):
    """Strict inbound payload model protecting downstream AI embedding tensors."""
    platform: AvailablePlatforms = Field(
        description="The technical ecosystem origin (e.g., Windows, Linux, Identity Provider, AWS)."
    )
    raw_log: str = Field(
        max_length=12000,  # Safety guard preventing adversarial memory bloat (OOM)
        description="The raw string content or sequential sequence log batch to evaluate."
    )


    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: str) -> str:
        """Normalizes case, trims whitespace, and converts '-' or '_' delimiters into spaces."""
        return " ".join(value.replace("_", " ").replace("-", " ").split()).lower()
