import logging

from src.llm.interfaces import ILlmEngine
from src.soc_agent.prompt_factory import PromptFactory
from src.soc_agent.schemas import GuardLayerVerdict

logger = logging.getLogger(__name__)


class SocAgent:
    """
    Core AI Threat Hunter Agent orchestrating multi-stage forensic analysis.
    Operates agnostically using loose interface boundaries (ILlmEngine)
    and returns rigid, deterministic semantic contracts.
    """

    def __init__(self, llm_engine: ILlmEngine):
        """
        Injects the LLM Engine interface, ensuring full structural decoupling
        from specific providers like Ollama.
        """
        self._llm_engine = llm_engine

    def analyze_ingress_flow(self, platform: str, raw_log: str) -> GuardLayerVerdict:
        """
        First-stage (Guard Layer) triage analysis.
        Leverages native English expert prompts to filter nominal activity
        and extract high-impact attack signatures for the vector store.

        :param platform: Target ecosystem (e.g., Windows, AWS, Identity Provider)
        :param raw_log: Raw string dataset or log batch sequence
        :return: Typesafe Pydantic validation schema instance
        """
        logger.info(
            f"[SOC AGENT] Single-pass Guard Layer analysis triggered for platform: '{platform}'"
        )

        try:
            prompt = PromptFactory.build_guard_layer_prompt(
                platform=platform, raw_log=raw_log
            )
            return self._llm_engine.analyze_event(
                prompt=prompt, response_schema=GuardLayerVerdict
            )
        except Exception as e:
            logger.error(f"[SOC AGENT] Semantic triage flow collapsed: {e!s}")
            raise
