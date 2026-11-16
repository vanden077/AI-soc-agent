import logging

from src.embedding.interfaces import IEmbeddingEngine
from src.persistence.interfaces import IVectorSearchEngine
from src.soc_agent.schemas import MitreTechnique, ThreatAnalysis
from src.soc_agent.schemas import GuardLayerVerdict
from src.api.schemas import AvailablePlatforms
from src.llm.interfaces import ILlmEngine
from src.soc_agent.agent import SocAgent

logger = logging.getLogger(__name__)

class SocAgentWorkflow:
    """
    Core Domain AI Workflow.
    Orchestrates single-pass Guard Layer LLM triage followed by platform-filtered
    KNN semantic retrieval against the MITRE ATT&CK vector store.
    """

    def __init__(
        self,
        llm_engine: ILlmEngine,
        embedding_engine: IEmbeddingEngine,
        vector_engine: IVectorSearchEngine,
        knn_limit: int = 5,
        min_similarity: float = 0.45,
        similarity_delta: float = 0.035,
    ) -> None:
        self._agent = SocAgent(llm_engine=llm_engine)
        self._embedding_engine = embedding_engine
        self._vector_engine = vector_engine
        self._knn_limit = knn_limit
        self._min_similarity = min_similarity
        self._similarity_delta = similarity_delta

    async def execute(self, platform: AvailablePlatforms, raw_log: str) -> ThreatAnalysis:
        """
        Executes the full forensic pipeline:
        - Step 1: Qualify raw log via Guard Layer LLM inference.
        - Step 2: If threat detected, retrieve and filter the closest MITRE ATT&CK techniques.
        """
        # [STEP 1] Guard Layer Triage
        verdict = self._qualify_raw_log(platform=platform, raw_log=raw_log)

        if not verdict.is_threat or not verdict.semantic_summary:
            logger.info(f"[AGENT WORKFLOW] Benign activity confirmed for '{platform.value}'. Skipping KNN.")
            return ThreatAnalysis(
                platform=platform,
                is_threat=False,
                confidence_score=verdict.confidence_score,
                semantic_summary=None,
                matched_techniques=[],
            )

        # [STEP 2] Query Vectorization, Platform-Filtered KNN Retrieval & Adaptive Filtering
        matched_techniques = self._retrieve_mitre_techniques(
            platform=platform,
            semantic_summary=verdict.semantic_summary,
        )

        return ThreatAnalysis(
            platform=platform,
            is_threat=True,
            confidence_score=verdict.confidence_score,
            semantic_summary=verdict.semantic_summary,
            matched_techniques=matched_techniques,
        )

    def _qualify_raw_log(self, platform: AvailablePlatforms, raw_log: str) -> GuardLayerVerdict:
        """Step 1: Ask LLM to determine if there is a threat and extract semantic signature."""
        logger.info(f"[AGENT WORKFLOW] Initiating Guard Layer triage for platform: '{platform.value}'")
        return self._agent.analyze_ingress_flow(
            platform=platform.value,
            raw_log=raw_log,
        )

    def _retrieve_mitre_techniques(
        self,
        platform: AvailablePlatforms,
        semantic_summary: str,
    ) -> list[MitreTechnique]:
        """Step 2: Execute platform-filtered KNN search and keep closely clustered top matches."""
        logger.info(f"[AGENT WORKFLOW] Running KNN MITRE lookup for platform: '{platform.value}'")

        query_vector = self._embedding_engine.embed_query(text=semantic_summary)

        raw_matches = self._vector_engine.similarity_search(
            query_vector=query_vector,
            response_model=MitreTechnique,
            filter_expression={"platforms": platform.value},
            limit=self._knn_limit,
        )

        return self._filter_close_matches(raw_matches)

    def _filter_close_matches(self, matches: list[MitreTechnique]) -> list[MitreTechnique]:
        """
        Retains the top candidate (if above min_similarity) and any subsequent candidates
        whose normalized similarity remains within `similarity_delta` of the best score.
        """
        if not matches:
            return []

        # sort matched techniques by normalized similarity DESC
        sorted_matches = sorted(matches, reverse=True)
        top_score = sorted_matches[0].normalized_similarity

        if top_score < self._min_similarity:
            logger.warning(
                f"[AGENT WORKFLOW] Top MITRE match similarity ({top_score:.3f}) "
                f"below floor threshold ({self._min_similarity}). Discarding weak matches."
            )
            return []

        cutoff = max(self._min_similarity, top_score - self._similarity_delta)
        filtered = [m for m in sorted_matches if m.normalized_similarity >= cutoff]

        logger.info(
            f"[AGENT WORKFLOW] Kept {len(filtered)}/{len(sorted_matches)} MITRE techniques "
            f"(top_score={top_score:.3f}, cutoff={cutoff:.3f})."
        )
        return filtered