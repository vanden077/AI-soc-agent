import pytest
from copy import deepcopy
from typing import Any

from soc_agent.schemas import EventAnalysis, SeverityLevel, MitreAttackCorrelation, RemediationAction
from tests.dataset_test import (
    EVENT_ANALYSIS_SCHEMA,
    MITRE_ATTACK_CORRELATION_SCHEMA,
)
from pydantic import ValidationError




# dataset manipulations for covering all test cases
def _get_nominal_critical_threat() -> dict[str, Any]:
    """Add MITRE correlation to event"""
    test_case = deepcopy(EVENT_ANALYSIS_SCHEMA)
    test_case["mitre_correlations"] = [MITRE_ATTACK_CORRELATION_SCHEMA]
    return test_case


def _get_nominal_threat_with_emtpy_mitre_list() -> dict[str, Any]:
    """Return an event without MITRE correlation"""
    return deepcopy(EVENT_ANALYSIS_SCHEMA)


def _get_error_invalid_severity_value() -> dict[str, Any]:
    """Return an event with invalid severity value"""
    test_case = deepcopy(EVENT_ANALYSIS_SCHEMA)
    test_case["revised_severity"] = "VERY_HIGH"
    return test_case


def _get_error_payload_pollution() -> dict[str, Any]:
    """Return an event with an unexpected field"""
    test_case = deepcopy(EVENT_ANALYSIS_SCHEMA)
    test_case["unexpected_hacker_key"] = "injected_data"
    return test_case


def _get_error_missing_required_fields() -> dict[str, Any]:
    """Return an event with missing required fields"""
    test_case = deepcopy(EVENT_ANALYSIS_SCHEMA)
    test_case.pop("revised_severity")
    return test_case


# parametrized test cases
TEST_CASES_EVENT = [
    (
        "Nominal Critical Threat",
        _get_nominal_critical_threat(),
        True,
        None,
    ),
    (
        "Nominal Threat with Empty MITRE List",
        _get_nominal_threat_with_emtpy_mitre_list(),
        True,
        None,
    ),
    (
        "Error: Invalid Severity StrEnum Value",
        _get_error_invalid_severity_value(),
        False,
        ("revised_severity",),
    ),
    (
        "Error: Payload Pollution (Extra Fields Forbidden)",
        _get_error_payload_pollution(),
        False,
        ("unexpected_hacker_key",),
    ),
    (
        "Error: Missing Required Field",
        _get_error_missing_required_fields(),
        False,
        ("revised_severity",),
    ),
]


@pytest.mark.parametrize(
    "test_name, payload, should_pass, expected_error_msg", TEST_CASES_EVENT
)
def test_event_analysis_schema(test_name, payload, should_pass, expected_error_msg):
    """Unified matrix test validating schema behavior via Pydantic v2 model_validate."""
    if should_pass:
        # Idiomatic Pydantic v2 validation without dict unpacking parsing issues
        analysis = EventAnalysis.model_validate(payload)
        assert analysis.is_threat == payload["is_threat"]
        assert analysis.revised_severity == SeverityLevel(payload["revised_severity"])
        assert analysis.justification == payload["justification"]

        assert analysis.mitre_correlations == [
            MitreAttackCorrelation.model_validate(x)
            for x in payload["mitre_correlations"]  # type: ignore
        ]
        assert analysis.suggested_action == RemediationAction(
            payload["suggested_action"]
        )
    else:
        with pytest.raises(ValidationError) as err:
            EventAnalysis.model_validate(payload)
        assert err.value.errors()[0]["loc"] == expected_error_msg


# --- ANTI-MUTATION SECURITY LOCK ---
def test_event_analysis_immutability():
    """Ensures the object is deeply frozen and cannot be mutated by downstream nodes."""
    _, nominal_payload, _, _ = TEST_CASES_EVENT[0]

    # Clean validation, perfectly typed for PyCharm's inference engine
    analysis = EventAnalysis.model_validate(nominal_payload)

    with pytest.raises(ValidationError, match="Instance is frozen"):
        analysis.is_threat = True  # type: ignore
