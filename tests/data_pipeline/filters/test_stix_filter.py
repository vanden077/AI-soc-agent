import pytest
from src.data_pipeline.filters.stix_filter import StixFilter

from tests.dataset_test import STIX_MOCK


def test_stix_filter_accepts_active_root_technique():
    """
    Nominal Case: A standard active attack pattern technique (e.g., T1055 Process Injection).
    Must evaluate to True since it is a valid dict, type is 'attack-pattern', and is active.
    """
    # STIX_MOCK["objects"][0] is 'Process Injection' (active root technique)
    stix_obj = STIX_MOCK["objects"][0]
    stix_filter = StixFilter(stix_object=stix_obj)
    assert stix_filter.is_valid_technique() is True


def test_stix_filter_accepts_active_sub_technique():
    """
    Nominal Case: A standard active sub-technique (e.g., T1055.001 DLL Injection).
    Must evaluate to True since our code architecture includes sub-techniques in the VSS topology.
    """
    # STIX_MOCK["objects"][1] is 'Dynamic Link Library Injection' (active sub-technique)
    stix_obj = STIX_MOCK["objects"][1]
    stix_filter = StixFilter(stix_object=stix_obj)
    assert stix_filter.is_valid_technique() is True


def test_stix_filter_rejects_deprecated_objects():
    """
    Edge Case: An attack-pattern that has been officially deprecated (e.g., T1119 Automated Collection).
    Must evaluate to False through short-circuit lifecycle guardrails.
    """
    # STIX_MOCK["objects"][2] is marked as "deprecated": True
    stix_obj = STIX_MOCK["objects"][2]
    stix_filter = StixFilter(stix_object=stix_obj)
    assert stix_filter.is_valid_technique() is False


def test_stix_filter_rejects_revoked_objects():
    """
    Edge Case: An attack-pattern that has been officially revoked (e.g., T1179 Hooking).
    Must evaluate to False through short-circuit lifecycle guardrails.
    """
    # STIX_MOCK["objects"][3] is marked as "revoked": True
    stix_obj = STIX_MOCK["objects"][3]
    stix_filter = StixFilter(stix_object=stix_obj)
    assert stix_filter.is_valid_technique() is False


def test_stix_filter_rejects_non_attack_pattern_types():
    """
    Edge Case: A structurally valid STIX node that is not an attack-pattern (e.g., APT28 Intrusion Set).
    Must evaluate to False to isolate only technical procedures semantics.
    """
    # STIX_MOCK["objects"][4] is an "intrusion-set"
    stix_obj = STIX_MOCK["objects"][4]
    stix_filter = StixFilter(stix_object=stix_obj)
    assert stix_filter.is_valid_technique() is False


@pytest.mark.parametrize(
    "corrupted_payload",
    ["corrupted_string_instead_of_dict", ["list", "of", "elements"], None, 12345],
)
def test_stix_filter_defensive_guardrail_against_invalid_payload_types(
    corrupted_payload, caplog
):
    """
    Edge Case: The stream injector passes a corrupted or malformed non-dictionary payload.
    The filter must gracefully capture it, log a warning diagnostic, and safely return False.
    """
    # When
    stix_filter = StixFilter(stix_object=corrupted_payload)
    result = stix_filter.is_valid_technique()

    # Then
    assert result is False
    assert "Evicting STIX object: Invalid payload type" in caplog.text
    assert f"Expected dict, got {type(corrupted_payload).__name__}" in caplog.text
