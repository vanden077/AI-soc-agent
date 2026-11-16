import logging

from src.llm.interfaces import ILlmEngine
from src.llm import LlmManager
from src.constants import Settings

logger = logging.getLogger(__name__)

def init_llm(settings: Settings) -> ILlmEngine:
    """Start LLM"""
    try:
        logger.info(f"[LLM STARTUP] Load LLM {settings.LLM_ENGINE}, model {settings.LLM_MODEL}...")
        llm = LlmManager(
            base_url=settings.LLM_URL,
            llm_engine=settings.LLM_ENGINE,
            llm_model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE
        )
        return llm.engine
    except Exception as e:
        logger.error(f"[LLM STARTUP] LLM initialization failed because: {str(e)}")
        raise e
