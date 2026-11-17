import logging
from uuid import uuid4

from fastapi import HTTPException, status

from src.api.schemas import (
    AnalysisJobRecord,
    AnalysisQueuedResponse,
    JobStatus,
    LogIngressPayload,
)
from src.persistence.interfaces import IJsonStorageEngine, IQueueEngine

logger = logging.getLogger(__name__)


class AnalysisQueueService:
    """
    Application service managing asynchronous log ingestion, queue throttling,
    and initial job persistence before background worker execution.
    """

    def __init__(
            self,
            json_engine: IJsonStorageEngine,
            queue_engine: IQueueEngine,
            max_pending_size: int = 50,
            job_ttl: int = 86_400,
    ) -> None:
        self._json_engine = json_engine
        self._queue_engine = queue_engine
        self._max_pending_size = max_pending_size
        self._job_ttl = job_ttl

    def submit_log(self, payload: LogIngressPayload) -> AnalysisQueuedResponse:
        """Orchestrate backpressure check, job persistence, and FIFO queue admission."""
        self._ensure_queue_capacity()

        job_id = str(uuid4())
        self._persist_initial_job(job_id=job_id, payload=payload)
        queue_size = self._enqueue_with_rollback(job_id=job_id)

        logger.info(
            f"[QUEUE SERVICE] Enqueued job {job_id} for platform {payload.platform} (queue_size={queue_size}).",
        )
        return AnalysisQueuedResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            queue_size=queue_size,
        )

    def _ensure_queue_capacity(self) -> None:
        """Verify queue broker availability and enforce anti-DoS backpressure limits."""
        try:
            current_size = self._queue_engine.pending_size()
        except Exception as err:
            logger.error(f"[QUEUE SERVICE] Failed to query pending queue size: {err!s}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if current_size >= self._max_pending_size:
            logger.warning(
                f"[QUEUE SERVICE] Rejecting ingress log: pending queue reached capacity ({self._max_pending_size}).",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Analysis queue capacity reached. Please retry later.",
            )

    def _persist_initial_job(self, job_id: str, payload: LogIngressPayload) -> None:
        """Persist the initial PENDING job record in JSON storage."""
        job_key = f"job:{job_id}"
        record = AnalysisJobRecord(
            job_id=job_id,
            status=JobStatus.PENDING,
            log_ingress_payload=payload,
        )
        inserted = self._json_engine.insert(
            key=job_key,
            data=record.model_dump(mode="json"),
            ttl=self._job_ttl,
        )
        if not inserted:
            logger.error(f"[QUEUE SERVICE] Failed to persist initial job record '{job_key}'.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _enqueue_with_rollback(self, job_id: str) -> int:
        """Push job_id onto the pending queue and rollback JSON storage if enqueuing fails."""
        try:
            return self._queue_engine.enqueue(job_id)
        except Exception as err:
            logger.error(f"[QUEUE SERVICE] Failed to enqueue job '{job_id}', rolling back JSON record: {err!s}")
            self._json_engine.delete(f"job:{job_id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
