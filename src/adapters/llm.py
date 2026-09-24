import logging
from typing import cast

from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from pydantic import ValidationError

from src.models import SiemAlertState
from src.schemas import EventAnalysis

logger = logging.getLogger()


class OllamaAdapter:
    """
    Adapter for interacting with Ollama.
    Guarantees structured and deterministic output compliant with EventAnalysis.
    """

    def __init__(
        self, model_name: str = "llama3.1", base_url: str = "http://localhost:11434"
    ):
        self.model_name = model_name
        self.base_url = base_url
        # Single private call initializing the bounded structured model execution path
        self.structured_llm = self._init_structured_model()

    def _init_structured_model(self) -> Runnable:
        """Private initialization method to allow clean mocking boundaries for structured output.

        Returns:
            A LangChain Runnable configured with Pydantic grammar schemas.
        """
        base_llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.0,
        )
        return base_llm.with_structured_output(EventAnalysis)

    @staticmethod
    def _format_messages(state: SiemAlertState) -> list[tuple[str, str]]:
        """
        Prepares and formats system and user messages for the LLM.
        """
        system_prompt = (
            "You are a senior SOC analyst and expert threat hunter.\n"
            "Analyze the provided SIEM alert and correlated logs to produce a strictly structured event analysis.\n\n"
            "Mandatory rules:\n"
            "1. Rely only on clear facts from the input data.\n"
            "2. Fill every required field in the analysis schema.\n"
            "3. Do not invent extra fields (the output schema forbids unknown properties)."
        )

        user_content = (
            f"--- INITIAL SIEM ALERT ---\n{state['raw_alert']}\n\n"
            f"--- SELECTED CORRELATED LOGS ---\n{state['correlated_logs']}"
        )

        return [("system", system_prompt), ("user", user_content)]

    def analyze_event(self, state: SiemAlertState) -> EventAnalysis:
        """
        Analyzes the current SIEM alert state and returns a valid EventAnalysis instance.

        Raises:
            ValidationError: If the LLM output violates Pydantic v2 constraints (extra='forbid').
            Exception: For connection or Ollama API failures.
        """
        messages = self._format_messages(state)

        try:
            logger.info("Sending alert data to Ollama for structured analysis...")

            # Use typing.cast to resolve the IDE type inference warning safely
            raw_result = self.structured_llm.invoke(messages)
            analysis_result = cast(EventAnalysis, raw_result)

            logger.info("Event analysis successfully generated and validated.")
            return analysis_result

        except ValidationError as ve:
            logger.error(f"Pydantic validation failed on LLM output: {ve.json()}")
            raise ve
        except Exception as e:
            logger.error(f"Ollama API call failed: {str(e)}")
            raise e
