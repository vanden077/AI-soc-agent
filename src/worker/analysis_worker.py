import asyncio
import logging

from src.api.schemas import AnalysisJobRecord, JobStatus
from src.api.services import ForensicService, JobProgressService
from src.embedding.interfaces import IEmbeddingEngine
from src.llm.interfaces import ILlmEngine
from src.persistence.interfaces import (
    IJsonStorageEngine,
    IQueueEngine,
    IVectorSearchEngine,
)
from src.soc_agent.schemas import ThreatAnalysis

logger = logging.getLogger(__name__)


class AnalysisWorker:
    """
    Background FIFO consumer executing CPU-bound SOC forensic workflows
    off the main ASGI event loop so HTTP endpoints remain responsive.
    """

    def __init__(
            self,
            json_engine: IJsonStorageEngine,
            queue_engine: IQueueEngine,
            llm_engine: ILlmEngine,
            embedding_engine: IEmbeddingEngine,
            vector_engine: IVectorSearchEngine,
            job_key_prefix: str,
            job_ttl: int = 86_400,
            poll_interval: float = 0.5,
            progress_service: JobProgressService | None = None,
    ) -> None:
        self._json_engine = json_engine
        self._queue_engine = queue_engine
        self._llm_engine = llm_engine
        self._embedding_engine = embedding_engine
        self._vector_engine = vector_engine
        self._job_key_prefix = job_key_prefix
        self._job_ttl = job_ttl
        self._poll_interval = poll_interval
        self._progress_service = progress_service

    async def run(self) -> None:
        """Continuously poll the pending queue until canceled on application shutdown."""
        logger.info("[ANALYSIS WORKER] Background forensic worker started.")
        try:
            while True:
                processed = await self.process_next_job()
                if not processed:
                    await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            logger.info("[ANALYSIS WORKER] Background forensic worker stopped.")
            raise

    async def process_next_job(self) -> bool:
        """Pop and process a single job from the pending queue. Returns False if queue is empty."""
        job_key = await asyncio.to_thread(self._queue_engine.dequeue)
        if job_key is None:
            return False

        record = await self._load_job(job_key=job_key)
        if record is None:
            return True

        # If progress service is bound, increment its internal counter and notify WebSocket
        if self._progress_service is not None:
            self._progress_service.job_started()
            await self._progress_service.notify_progress()

        try:
            await self._update_status(record=record, status=JobStatus.PROCESSING)

            try:
                analysis = await self._execute_forensic_workflow(record=record)
                record.analysis = analysis
                await self._update_status(record=record, status=JobStatus.COMPLETED)
                logger.info(f"[ANALYSIS WORKER] Job {record.job_id} completed successfully.")
            except Exception as err:
                logger.error(f"[ANALYSIS WORKER] Job {record.job_id} failed: {err!s}")
                record.error = "Forensic analysis failed."
                await self._update_status(record=record, status=JobStatus.FAILED)

            await asyncio.to_thread(self._queue_engine.mark_done, job_key)
        finally:
            # Notify WebSocket that job is finished, and calculate new X/Y done.
            if self._progress_service is not None:
                self._progress_service.job_finished()
                await self._progress_service.notify_progress()

        return True

    async def _load_job(self, job_key: str) -> AnalysisJobRecord | None:
        """Retrieve and validate the persisted job payload from JSON storage."""
        raw_data = await asyncio.to_thread(self._json_engine.get, job_key)
        if raw_data is None:
            logger.warning(f"[ANALYSIS WORKER] Job '{job_key}' missing or expired in JSON storage, skipping.")
            return None
        return AnalysisJobRecord.model_validate(raw_data)

    async def _update_status(self, record: AnalysisJobRecord, status: JobStatus) -> None:
        """Update job status and persist the updated record in JSON storage."""
        record.status = status
        await asyncio.to_thread(
            self._json_engine.insert,
            key=f"{self._job_key_prefix}{record.job_id}",
            data=record.model_dump(mode="json"),
            ttl=self._job_ttl,
        )

    async def _execute_forensic_workflow(
            self, record: AnalysisJobRecord
    ) -> ThreatAnalysis:
        """Run the synchronous AI correlation pipeline inside a dedicated worker thread."""
        forensic_service = ForensicService(
            llm_engine=self._llm_engine,
            embedding_engine=self._embedding_engine,
            vector_engine=self._vector_engine,
        )
        return await asyncio.to_thread(
            asyncio.run,
            forensic_service.analyze_and_report(
                platform=record.log_ingress_payload.platform,
                raw_log=record.log_ingress_payload.raw_log,
            ),
        )
