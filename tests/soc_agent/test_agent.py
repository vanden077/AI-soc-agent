import logging
from unittest.mock import MagicMock

import pytest

from src.llm.interfaces import ILlmEngine
from src.soc_agent.agent import SocAgent
from src.soc_agent.prompt_factory import PromptFactory
from src.soc_agent.schemas import GuardLayerVerdict


def test_analyze_ingress_flow_nominal_delegates_to_llm_engine(
    mocker,
    caplog,
) -> None:
    """Nominal: builds guard layer prompt, calls llm_engine.analyze_event, and returns verdict."""
    with caplog.at_level(logging.INFO):
        mock_llm_engine: MagicMock = mocker.MagicMock(spec=ILlmEngine)
        expected_prompt = [("system", "system prompt"), ("user", "user log")]
        expected_verdict = GuardLayerVerdict(
            is_threat=True,
            confidence_score=0.92,
            semantic_summary="Suspicious PowerShell execution attempting LSASS credential dumping.",
        )

        spy_prompt = mocker.patch.object(
            PromptFactory,
            "build_guard_layer_prompt",
            return_value=expected_prompt,
        )
        mock_llm_engine.analyze_event.return_value = expected_verdict

        agent = SocAgent(llm_engine=mock_llm_engine)
        verdict = agent.analyze_ingress_flow(
            platform="windows",
            raw_log="EventID=10 TargetImage=lsass.exe",
        )

        spy_prompt.assert_called_once_with(
            platform="windows",
            raw_log="EventID=10 TargetImage=lsass.exe",
        )
        mock_llm_engine.analyze_event.assert_called_once_with(
            prompt=expected_prompt,
            response_schema=GuardLayerVerdict,
        )
        assert verdict == expected_verdict
        assert "[SOC AGENT] Single-pass Guard Layer analysis triggered for platform: 'windows'" in caplog.text


def test_analyze_ingress_flow_logs_and_reraises_on_exception(
    mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Error: logs diagnostic message and re-raises exception when triage fails."""
    with caplog.at_level(logging.ERROR):
        mock_llm_engine: MagicMock = mocker.MagicMock(spec=ILlmEngine)
        mocker.patch.object(
            PromptFactory,
            "build_guard_layer_prompt",
            return_value=[("system", "s"), ("user", "u")],
        )
        mock_llm_engine.analyze_event.side_effect = RuntimeError("LLM inference timeout")

        agent = SocAgent(llm_engine=mock_llm_engine)

        with pytest.raises(RuntimeError, match="LLM inference timeout"):
            agent.analyze_ingress_flow(
                platform="windows",
                raw_log="EventID=10 TargetImage=lsass.exe",
            )

        assert "[SOC AGENT] Semantic triage flow collapsed: LLM inference timeout" in caplog.text