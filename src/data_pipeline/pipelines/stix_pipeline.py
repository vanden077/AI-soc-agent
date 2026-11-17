import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import ijson

from src.data_pipeline.compilers.stix_compiler import StixCompiler
from src.data_pipeline.extractors.stix_extractor import StixExtractor
from src.data_pipeline.filters.stix_filter import StixFilter
from src.embedding.interfaces import IEmbeddingEngine
from src.persistence.interfaces import IVectorIngestionEngine

logger = logging.getLogger(__name__)


class StixPipeline:
    """
    Synchronous data pipeline orchestrator optimized for RAM O(1) streaming execution.
    Consumes raw heavy STIX 2.1 JSON files incrementally, pipe-lining filtering,
    extraction, and compilation directly into flat native Python dictionaries.

    This pipeline has been implemented on a laptop without GPU and a small I5-1021OU @ 1.60Ghz...
    Batch size 50 is the sweet spot for a small CPU.

    ARCHITECTURAL NOTE ON PERFORMANCE & HARDWARE SCALE:
    The embedding engine (LangChain/PyTorch) is the absolute compute-bound bottleneck
    of this pipeline (~95% of execution time). Under current low-spec mobile CPU
    constraints, forcing multi-threading via torch.set_num_threads(4) degrades performance.

    INFRASTRUCTURE SCALE-UP STRATEGY:
    When deploying to heavy production infrastructure (e.g., Server CPUs or NVIDIA GPUs):
    1. CPU-Bound: Increase `torch.set_num_threads(N)` to leverage modern AVX-512/AMX cores.
    2. GPU-Bound: Switch the embedding device to "cuda". Matrix computation cycles
       will drop to milliseconds, scaling throughput exponentially.
    3. Tuning: Re-evaluate `batch_size` to 256 or higher once compute barriers are removed.
    """

    def __init__(
            self,
            cache_client: IVectorIngestionEngine,
            embedding_engine: IEmbeddingEngine,
            file_path: Path,
            batch_size: int = 50,
    ) -> None:
        """
        Initializes the pipeline with required infrastructure and active embedding engine.
        """
        self.cache_client = cache_client
        self.embedding_engine = embedding_engine
        self._file_path = file_path
        self._batch_size: int = batch_size
        self._remote_hashes: dict[str, str] = {}

    def run(self) -> None:
        """
        Pipeline entry point.
        Coordinates the 7-step ingestion sequence:

        1-Collect hashes
        2-Read file through ijson
            a-filter and extract data
            b-make a hash comparison (if hashes are equal skip object, it is already up to date)
            c-if you reach this point, object need an upsert, compile it through StixCompiler
            d-build a batch of self._batch_size and yield it

        3-Compute embedding batches by batches
        4-Execute bulk upsert to Redis
        5-Update semantic hashes
        """
        try:
            if not self._file_path.exists():
                raise FileNotFoundError(
                    f"Target STIX file not found at: {self._file_path}"
                )

            # [Step 1]
            self._remote_hashes = self.cache_client.fetch_remote_hashes()
            # [Step 2 a.b.c.d]
            batch_generator = self._build_batches()

            try:
                for batch_idx, (batch_buffer, text_embedding_buffer) in enumerate(
                        batch_generator, start=1
                ):
                    # Capture batch boundaries for observability
                    start_mitre_id = batch_buffer[0]["id"]
                    end_mitre_id = batch_buffer[-1]["id"]

                    try:
                        # [Step 3]
                        embeddings = self.embedding_engine.embed_documents(
                            text_embedding_buffer
                        )
                        # [Step 4]
                        self.cache_client.execute_bulk_upsert(
                            payload=batch_buffer, embeddings=embeddings, id_field="id"
                        )
                        # [Step 5] ONLY the mutations of the current batch (1 RTT)
                        batch_signatures = {
                            doc["mitre_id"]: doc["semantic_hash"]
                            for doc in batch_buffer
                        }
                        self.cache_client.set_remote_hashes(batch_signatures)

                        logger.info(
                            f"Successfully processed batch #{batch_idx} [{start_mitre_id} -> {end_mitre_id}]"
                        )
                    except Exception as batch_err:
                        # Isolation guardrail: catch errors on the flight to print precision post-mortem state
                        logger.error(
                            f"CRITICAL: Ingestion failure encountered on Batch #{batch_idx}. "
                            f"Range: {start_mitre_id} to {end_mitre_id}. Reason: {batch_err}"
                        )
                        raise
            finally:
                batch_generator.close()
        except Exception as err:
            logger.error(f"Pipeline failed because: {err!s}")
            raise

    # ============================================================================
    # PRIVATE PIPELINE STEPS
    # ============================================================================
    def _build_batches(self) -> Generator[tuple[list[dict[str, Any]], list[str]]]:
        """[Step 2] Opens the linear JSON stream and manages the chunking."""
        batch_buffer: list[dict[str, Any]] = []
        text_embedding_buffer: list[str] = []
        objects_read: int = 0
        objects_kept: int = 0
        objects_up_to_date: int = 0
        objects_evicted: int = 0

        with open(self._file_path, "rb") as f:
            # streams the array tokens one by one under O(1) RAM constraints
            stix_objects = ijson.items(f, "objects.item")

            for stix_object in stix_objects:
                objects_read += 1
                # [Step 2.a]
                extracted_data = self._filter_extract_stix_object(
                    stix_object=stix_object
                )

                if extracted_data is None:
                    objects_evicted += 1
                    continue

                # [Step 2.b]
                if not self._need_upsert(extracted_data=extracted_data):
                    objects_up_to_date += 1
                    continue

                # [Step 2.c]
                stix_compiler = StixCompiler(extracted_data=extracted_data)
                compiled_payload = stix_compiler.compile_fields()

                # [Step 2.d]
                objects_kept += 1
                batch_buffer.append(compiled_payload)
                text_embedding_buffer.append(compiled_payload["compiled_text"])

                if len(batch_buffer) == self._batch_size:
                    yield batch_buffer, text_embedding_buffer
                    batch_buffer = []
                    text_embedding_buffer = []

            # Flush any remaining entries hanging in the tail buffer
            if batch_buffer:
                yield batch_buffer, text_embedding_buffer

        logger.info(
            f"Successfully processed STIX Bundle stream: {self._file_path.name}"
        )
        logger.info(
            f"{objects_read} objects read, "
            f"{objects_kept} objects kept, "
            f"{objects_up_to_date} objects already up to date, "
            f"{objects_evicted} objects evicted"
        )

    @staticmethod
    def _filter_extract_stix_object(
            stix_object: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        From a given stix object extracted from stix document,
        check object is valid (not deprecated, and is an attack pattern)
        :return: dict[str, Any] if object is valid, else None
        """
        if not StixFilter(stix_object=stix_object).is_valid_technique():
            return None

        try:
            return StixExtractor(stix_object=stix_object).extract_fields()
        except ValueError as err:
            logger.debug(f"Evicting malformed STIX object because: {err}")
            return None

    def _need_upsert(self, extracted_data: dict[str, Any]) -> bool:
        """
        From a given stix object extracted from stix document, and filtered by _filter_extract_stix_object
        get its semantic_hash and compare it to self._remote_hashes.
        :return: boolean, True if object need upsert (so go into current batch), else False
        """
        if extracted_data["mitre_id"] not in self._remote_hashes:
            return True
        return (
                extracted_data["semantic_hash"]
                != self._remote_hashes[extracted_data["mitre_id"]]
        )
