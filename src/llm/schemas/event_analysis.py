from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

from .mitre_attack_correlation import MitreAttackCorrelation


class SeverityLevel(StrEnum):
    """Strict severity classification levels for operational triage."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RemediationAction(StrEnum):
    """Deterministic automated remediation playbooks."""

    ISOLATE_HOST = "ISOLATE_HOST"
    KILL_PROCESS = "KILL_PROCESS"
    MONITOR = "MONITOR"
    IGNORE = "IGNORE"


class EventAnalysis(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # Prevents mutation after instantiation
        extra="forbid",  # STRICTLY triggers a ValidationError on extra payload fields
    )

    """Schema representing the raw surgical analysis of a SIEM alert by the LLM agent."""
    is_threat: bool = Field(
        description="Binary verdict. True if the host behavior exhibits malicious intent or confirmed hostile anomalies."
    )
    revised_severity: SeverityLevel = Field(
        description="The agent's strictly validated reassessed severity level."
    )
    justification: str = Field(
        description="Concise, factual, engineering-focused reasoning explaining the verdict based on process arguments, network states, or indicators."
    )
    mitre_correlations: list[MitreAttackCorrelation] = Field(
        default=[],
        description="List of detected MITRE ATT&CK technics within the analyzed payload.",
    )
    suggested_action: RemediationAction = Field(
        description="The immediate automated remediation action recommended."
    )
