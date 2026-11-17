from pydantic import BaseModel, Field

from src.api.schemas import AvailablePlatforms
from src.soc_agent.schemas.mitre_technique import MitreTechnique


class ThreatAnalysis(BaseModel):
    """
    Unified end-to-end forensic report returned by the SOC workflow.
    Enforces a deterministic response structure whether the event is benign or malicious.
    """

    platform: AvailablePlatforms = Field(description="Target ecosystem analyzed.")
    is_threat: bool = Field(description="Verdict emitted by the Guard Layer.")
    confidence_score: float = Field(
        description="Guard Layer certainty score bounded between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
    )
    semantic_summary: str | None = Field(
        default=None,
        description="High-density technical summary generated when is_threat is True, otherwise null.",
    )
    matched_techniques: list[MitreTechnique] = Field(
        default_factory=list,
        description="Filtered Top-K MITRE ATT&CK candidate techniques ranked by semantic similarity.",
    )
