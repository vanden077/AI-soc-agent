from enum import StrEnum


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


class JobStatus(StrEnum):
    """Lifecycle states of an asynchronous SOC forensic analysis job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
