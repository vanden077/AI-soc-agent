from pydantic import BaseModel, Field


class MitreTechnique(BaseModel):
    """
    Domain model representing a single MITRE ATT&CK technique retrieved from RedisVL
    after semantic similarity scoring.
    """

    mitre_id: str = Field(
        description="Official MITRE ATT&CK Technique ID (e.g., T1055)."
    )
    parent_id: str | None = Field(
        default=None,
        description="Parent Technique ID if this entry is a sub-technique (e.g., T1055.001 -> T1055).",
    )
    technic_name: str = Field(description="Official MITRE ATT&CK Technique name.")
    tactics: str = Field(description="Associated MITRE ATT&CK kill-chain tactics.")
    description: str = Field(
        description="Technical description of the adversarial technique."
    )
    platforms: str = Field(description="Comma-separated list of applicable platforms.")
    normalized_similarity: float = Field(
        description="Normalized cosine similarity score clamped between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
    )

    def __lt__(self, other: "MitreTechnique") -> bool:
        """Here to easily compare two Mitre techniques by their normalized similarity."""
        return self.normalized_similarity < other.normalized_similarity
