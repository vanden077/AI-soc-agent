import logging
from collections.abc import Mapping

from fastapi import HTTPException, status

from src.api.schemas import AnalysisJobRecord, AnalysisQueuedResponse, JobStatus
from src.persistence.interfaces import IJsonStorageEngine, IQueueEngine

logger = logging.getLogger(__name__)


class JobQueryService:
    """
    Read-only application service (CQRS query side) responsible for retrieving
    pending/completed job queues and persisted forensic analysis records.
    """

    def __init__(
            self,
            json_engine: IJsonStorageEngine,
            queue_engine: IQueueEngine,
    ) -> None:
        self._json_engine = json_engine
        self._queue_engine = queue_engine

    def get_pending_jobs(self) -> list[AnalysisQueuedResponse]:
        """Return all pending jobs in FIFO order with current queue depth."""
        try:
            pending_ids = self._queue_engine.get_pending()
        except Exception as err:
            logger.error(f"[JOB QUERY SERVICE] Failed to retrieve pending jobs: {err!s}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        queue_size = len(pending_ids)
        return [
            AnalysisQueuedResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
                queue_size=queue_size,
            )
            for job_id in pending_ids
        ]

    def get_done_jobs(self) -> list[AnalysisJobRecord]:
        """Return all completed or failed analysis job records (most recent first)."""
        try:
            done_ids = self._queue_engine.get_done()
        except Exception as err:
            logger.error(f"[JOB QUERY SERVICE] Failed to retrieve done jobs: {err!s}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        records: list[AnalysisJobRecord] = []
        for job_id in done_ids:
            raw_record = self._json_engine.get(f"job:{job_id}")
            if isinstance(raw_record, Mapping):
                records.append(AnalysisJobRecord.model_validate(raw_record))
        return records

    def get_job(self, job_id: str) -> AnalysisJobRecord:
        """Retrieve a persisted analysis job record by identifier, raising 404 if absent or expired."""
        raw_record = self._json_engine.get(f"job:{job_id}")
        if not isinstance(raw_record, Mapping):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found or expired.",
            )
        return AnalysisJobRecord.model_validate(raw_record)
