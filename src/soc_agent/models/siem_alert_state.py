from typing import Any, TypedDict

from llm.schemas import EventAnalysis


class SiemAlertState(TypedDict):
    """
    Represents the immutable state of the soc_agent workflow.
    Defines the strict contract required for cyber event analysis.
    """

    raw_alert: dict[str, Any]
    correlated_logs: list[dict[str, Any]]
    analysis: EventAnalysis | None
    metadata: dict[str, Any]
