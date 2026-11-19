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
            max_pending_size: int,
            job_ttl: int,
            job_key_prefix: str,
    ) -> None:
        self._json_engine = json_engine
        self._queue_engine = queue_engine
        self._max_pending_size = max_pending_size
        self._job_ttl = job_ttl
        self._job_key_prefix = job_key_prefix

    def submit_log(self, payload: LogIngressPayload) -> AnalysisQueuedResponse:
        """Orchestrate backpressure check, job persistence, and FIFO queue admission."""
        self._ensure_queue_capacity()

        job_id = str(uuid4())
        job_key = f"{self._job_key_prefix}{job_id}"
        self._persist_initial_job(job_id=job_id, job_key=job_key, payload=payload)
        queue_size = self._enqueue_with_rollback(job_key=job_key)

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

    def _persist_initial_job(
            self, job_id: str, job_key: str, payload: LogIngressPayload
    ) -> None:
        """Persist the initial PENDING job record in JSON storage."""
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

    def _enqueue_with_rollback(self, job_key: str) -> int:
        """Push job_key onto the pending queue and rollback JSON storage if enqueuing fails."""
        try:
            return self._queue_engine.enqueue(job_key)
        except Exception as err:
            logger.error(f"[QUEUE SERVICE] Failed to enqueue job '{job_key}', rolling back JSON record: {err!s}")
            self._json_engine.delete(job_key)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
