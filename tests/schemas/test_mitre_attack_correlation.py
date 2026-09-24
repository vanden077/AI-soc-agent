from copy import deepcopy
from typing import Any

import pytest
from dataset_test import MITRE_ATTACK_CORRELATION_SCHEMA
from pydantic import ValidationError

from src.schemas import MitreAttackCorrelation


# dataset manipulations for covering all test cases
def _get_valid_mitre_attack() -> dict[str, Any]:
    """Return valid mitre attack correlation schema."""
    return deepcopy(MITRE_ATTACK_CORRELATION_SCHEMA)


def _get_falsy_mitre_attack(confidence_score: int) -> dict[str, Any]:
    """Return mitre attack correlation schema with an invalid confidence score."""
    test_case = deepcopy(MITRE_ATTACK_CORRELATION_SCHEMA)
    test_case["confidence_score"] = confidence_score
    return test_case


# parametrized test cases
TEST_CASES_MITRE_ATTACK = [
    (
        "Valid Mitre attack correlation schema",
        _get_valid_mitre_attack(),
        True,
        None,
    ),
    (
        "Falsy Mitre attack correlation schema, confidence score too high",
        _get_falsy_mitre_attack(6),
        False,
        ("confidence_score",),
    ),
    (
        "Falsy Mitre attack correlation schema, confidence score too low",
        _get_falsy_mitre_attack(-1),
        False,
        ("confidence_score",),
    ),
]


@pytest.mark.parametrize(
    "test_name, payload, should_pass, expected_error_msg", TEST_CASES_MITRE_ATTACK
)
def test_mitre_attack_schema(test_name, payload, should_pass, expected_error_msg):
    """Unified matrix test validating schema behavior via Pydantic v2 model_validate."""
    if should_pass:
        analysis = MitreAttackCorrelation.model_validate(payload)
        assert analysis.tactic == payload["tactic"]
        assert analysis.technic_id == payload["technic_id"]
        assert analysis.technic_name == payload["technic_name"]
        assert analysis.confidence_score == payload["confidence_score"]
    else:
        with pytest.raises(ValidationError) as err:
            MitreAttackCorrelation.model_validate(payload)
        assert err.value.errors()[0]["loc"] == expected_error_msg


def test_mitre_attack_immutability():
    """Ensures the object is deeply frozen and cannot be mutated by downstream nodes."""
    _, nominal_payload, _, _ = TEST_CASES_MITRE_ATTACK[0]

    analysis = MitreAttackCorrelation.model_validate(nominal_payload)

    with pytest.raises(ValidationError, match="Instance is frozen"):
        analysis.confidence_score = 2
