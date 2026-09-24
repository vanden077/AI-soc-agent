from copy import deepcopy

import pytest
from dataset_test import (
    EVENT_ANALYSIS_SCHEMA,
    MITRE_ATTACK_CORRELATION_SCHEMA,
    SIEM_ALERT_STATE_MODEL,
)

from src.models import SiemAlertState
from src.schemas import EventAnalysis


# dataset manipulations for covering all test cases
def _get_complete_siem_alert_state_model() -> SiemAlertState:
    """Return valid SiemAlertState with a valid event"""
    test_case = deepcopy(SIEM_ALERT_STATE_MODEL)
    event_test_case = deepcopy(EVENT_ANALYSIS_SCHEMA)
    event_test_case["mitre_correlations"] = [deepcopy(MITRE_ATTACK_CORRELATION_SCHEMA)]
    test_case["analysis"] = EventAnalysis(**event_test_case)
    return SiemAlertState(**test_case)


def _get_valid_siem_alert_state_with_none_event() -> SiemAlertState:
    """Return valid SiemAlertState with a None event."""
    return SiemAlertState(**deepcopy(SIEM_ALERT_STATE_MODEL))


# parametrized test cases
TEST_CASES_SIEM_ALERT_STATE = [
    (
        1,
        _get_complete_siem_alert_state_model(),
    ),
    (
        2,
        _get_valid_siem_alert_state_with_none_event(),
    ),
]


@pytest.mark.parametrize("test_id, payload", TEST_CASES_SIEM_ALERT_STATE)
def test_siem_alert_state_instantiation(test_id: int, payload: SiemAlertState):
    """
    Validate runtime instantiation and access of a correct SiemAlertState dictionary.
    """
    assert payload["raw_alert"] == SIEM_ALERT_STATE_MODEL["raw_alert"]
    assert payload["correlated_logs"] == SIEM_ALERT_STATE_MODEL["correlated_logs"]
    assert payload["metadata"] == SIEM_ALERT_STATE_MODEL["metadata"]

    match test_id:
        case 1:
            assert isinstance(payload["analysis"], EventAnalysis)
        case 2:
            assert payload["analysis"] is None
