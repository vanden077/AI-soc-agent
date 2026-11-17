from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.api.schemas.enums import JobStatus
from src.api.schemas.log_ingress_payload import LogIngressPayload
from src.soc_agent.schemas import ThreatAnalysis


class AnalysisJobRecord(BaseModel):
    """Persistent JSON document tracking a queued or completed forensic analysis job."""

    job_id: str = Field(description="Unique identifier (UUID4) assigned at ingestion.")
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Current execution state of the background analysis job.",
    )
    log_ingress_payload: LogIngressPayload = Field(description="Ingress log posted by user.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the job was ingested.",
    )
    analysis: ThreatAnalysis | None = Field(
        default=None,
        description="Final MITRE ATT&CK forensic report once status is 'completed'.",
    )
    error: str | None = Field(
        default=None,
        description="Diagnostic failure reason if status is 'failed'.",
    )


class AnalysisQueuedResponse(BaseModel):
    """Immediate HTTP 202 Accepted response returned upon asynchronous log ingestion."""

    job_id: str = Field(description="Unique identifier to poll job status and results.")
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Initial job state confirming queue admission.",
    )
    queue_size: int = Field(
        ge=1,
        description="Current number of pending jobs waiting in the analysis queue.",
    )
