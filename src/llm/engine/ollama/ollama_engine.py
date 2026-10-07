import logging
from typing import cast

from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from pydantic import ValidationError

from src.llm.models import SiemAlertState
from src.llm.schemas import EventAnalysis
from src.llm.common.i_llm_engine import ILlmEngine

logger = logging.getLogger()

class OllamaEngine(ILlmEngine):
    """LLM llama 3.1 engine"""
    def __init__(self, base_url: str, model_name: str, temperature: float = 0.0):
        self._base_url = base_url
        self._model_name = model_name
        self._temperature = temperature
        self._llm = self._init_llm()

    def _init_llm(self) -> Runnable:
        """initialization method to allow clean mocking boundaries for structured output."""
        base_llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=self._temperature,
        )
        return base_llm.with_structured_output(EventAnalysis)


    @staticmethod
    def _format_message(state: SiemAlertState) -> list[tuple[str, str]]:
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
        messages = self._format_message(state)

        try:
            logger.info("Sending alert data to Ollama for structured analysis...")

            # Use typing.cast to resolve the IDE type inference warning safely
            raw_result = self._llm.invoke(messages)
            analysis_result = cast(EventAnalysis, raw_result)

            logger.info("Event analysis successfully generated and validated.")
            return analysis_result

        except ValidationError as ve:
            logger.error(f"Pydantic validation failed on LLM output: {ve.json()}")
            raise ve
        except Exception as e:
            logger.error(f"Ollama API call failed: {str(e)}")
            raise e

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature
