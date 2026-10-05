from pydantic import BaseModel, ConfigDict, Field


class MitreAttackCorrelation(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # Prevents mutation after instantiation
        extra="forbid",  # STRICTLY triggers a ValidationError on extra payload fields
    )

    """Schema representing an explicit correlation with the MITRE ATT&CK framework."""

    tactic: str = Field(
        description="The primary identified MITRE ATT&CK tactic name (e.g., Execution, Persistence, Privilege Escalation)."
    )
    technic_id: str = Field(
        description="The unique MITRE technic or sub-technic identifier (e.g., T1059.003, T1543)."
    )
    technic_name: str = Field(
        description="The human-readable name of the associated technic (e.g., Windows Command Shell, System Service Creation)."
    )
    confidence_score: int = Field(
        ge=1,
        le=5,
        description="The agent's confidence level for this specific correlation (1: Very Low, 5: Absolute Certainty).",
    )
