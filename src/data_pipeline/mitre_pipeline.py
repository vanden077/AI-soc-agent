import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_redis import RedisConfig, RedisVectorStore
from .common.pipeline_utils import PipelineUtils
from .exceptions import MitreDownloadError
from .mitre_parser import MitreParser

logger = logging.getLogger(__name__)

# TODO use vector client as init parameters + update all unit tests.

class MitrePipeline(PipelineUtils):
    """Acts as an orchestrator for MITRE Attack JSON ingestion with indexed metadata fields."""
    def start_pipeline(self) -> None:
        """Main process orchestrator.

        :raises RuntimeError: If any critical stage of the pipeline fails.
        """
        try:
            logger.info("⚙️ Get MITRE JSON...")
            self._get_mitre_attack_stix_json()

            logger.info("⚙️ Prepare data for vectorization...")
            self._vector_docs = MitreParser.prepare_data_for_vectorization(
                MitreParser.parse_mitre_technics(self._mitre_json)
            )

            logger.info("⚙️ Start injection...")
            self._inject_data_into_redis()
            logger.info("🚀 Pipeline execution finished successfully.")

        except Exception as err:
            logger.critical(
                f"❌ failure in MITRE Ingestion Pipeline: {err}",
                exc_info=True,
            )
            raise RuntimeError(f"❌ MITRE Pipeline failed: {err}") from err

    def _get_mitre_attack_stix_json(self) -> None:
        """Check if MITRE JSON is present locally, valid, and up to date.

        :raises: MitreDownloadError
        """
        if not self.check_matrix_is_locally_cached():
            self.create_local_matrix()

        self._mitre_json = self.load_json_mitre_in_memory()

        if not self._mitre_json:
            logger.warning(
                "Local matrix cache is invalid or missing. Attempting fresh download..."
            )
            self.download_latest_mitre_version()
            self._mitre_json = self.load_json_mitre_in_memory()

            if not self._mitre_json:
                raise MitreDownloadError(
                    f"❌ MITRE JSON is not downloadable or invalid, process aborted. Please check: {self._mitre_json_path}"
                )

    def _inject_data_into_redis(self) -> None:
        """Inject vectorized documents into the Redis vector store with explicit TAG schema index fields."""
        logger.info("⚙️ Initializing HuggingFace Embeddings (all-MiniLM-L6-v2) on CPU...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        logger.info(f"⚙️ Building HNSW graph in Redis (Index: {self._index_name})...")

        # Enforcing TAG indices creation for hybrid pre-filtering capabilities
        config = RedisConfig(
            index_name=self._index_name,
            redis_url=self._redis_url,
            distance_metric="COSINE",
            indexing_algorithm="HNSW",
            metadata_schema=[
                {"name": "platforms", "type": "tag"},
                {"name": "tactics", "type": "tag"},
            ],
        )

        stable_ids = [doc.metadata["attack_code"] for doc in self._vector_docs]
        logger.info(
            f"⚙️ Streaming {len(self._vector_docs)} documents to Redis with stable IDs (UPSERT mode)..."
        )

        RedisVectorStore.from_documents(
            documents=self._vector_docs,
            embedding=embeddings,
            config=config,
            ids=stable_ids,
        )

        logger.info("⚙️ Redis Vector Store is fully initialized and synchronized.")
