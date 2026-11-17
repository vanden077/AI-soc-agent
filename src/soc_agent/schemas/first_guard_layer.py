from pydantic import BaseModel, Field


class GuardLayerVerdict(BaseModel):
    """
    This is an inner schema for communication with the LLM agent, it is not returned as a response to the user.
    Internal domain contract for single-pass triage and semantic extraction.
    Omitting 'semantic_summary' when is_threat is False saves CPU tokens
    and automatically resolves to the default nominal baseline.
    """

    is_threat: bool = Field(
        description=(
            "True ONLY if the raw log exhibits critical security state mutations, "
            "structural compromise, active defense evasion, unauthorized privilege escalation, "
            "or automated unauthorized egress. False for nominal activity."
        )
    )
    confidence_score: float = Field(
        description="Mathematical certainty strictly bounded between 0.0 and 1.0 based on behavioral evidence completeness.",
        ge=0.0,
        le=1.0,
    )
    semantic_summary: str | None = Field(
        default=None,
        description=(
            "MUST be null if is_threat is false. "
            "If is_threat is true, write ONE high-density technical sentence (25-40 words, max 280 chars) "
            "stating the attack mechanism, targeted artifact, and adversarial objective for vector similarity search."
        ),
        max_length=280,
    )
