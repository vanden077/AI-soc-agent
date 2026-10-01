from tests.dataset_test import STIX_MOCK
from langchain_core.documents import Document
from src.data_pipeline.mitre_parser import MitreParser


def test_parse_mitre_technics():
    """Ensure deprecated technics and non-attack-pattern profiles are strictly removed."""
    results = MitreParser.parse_mitre_technics(STIX_MOCK)

    assert isinstance(results, list)
    assert (
        len(results) == 1
    )  # we ensure that deprecated, revoked and not qualified tech is removed from result
    tech = results[0]
    assert isinstance(tech, dict)
    # assert keys are ok
    assert "id" in tech
    assert "name" in tech
    assert "description" in tech
    assert "tactics" in tech
    assert "platforms" in tech
    assert isinstance(tech["tactics"], list)
    assert isinstance(tech["platforms"], list)
    # assert values are ok
    assert tech["id"] == "T1055"
    assert tech["name"] == "Process Injection"
    assert (
        tech["description"] == "Adversaries may inject malicious code into processes."
    )
    assert "defense-evasion" in tech["tactics"]
    assert "privilege-escalation" in tech["tactics"]
    assert "windows" in tech["platforms"]


def test_parse_falsy_mitre_do_not_crash():
    """Ensure parsing a falsy or empty stix_json do not crash the entire program and just return an empty list."""
    # empty
    results_empty_stix_json = MitreParser.parse_mitre_technics({})
    assert isinstance(results_empty_stix_json, list)
    assert len(results_empty_stix_json) == 0
    # falsy
    result_falsy_stix_json = MitreParser.parse_mitre_technics(
        {"test": "i am not coming from mitre neither from github."}
    )
    assert isinstance(result_falsy_stix_json, list)
    assert len(result_falsy_stix_json) == 0


def test_prepare_data_for_vectorization():
    """Check data parsed by parse_mitre_technics are correctly split for vectorization."""
    result = MitreParser.prepare_data_for_vectorization(
        MitreParser.parse_mitre_technics(STIX_MOCK)
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Document)

    assert (
        result[0].page_content
        == "Technic: Process Injection (T1055). Description: Adversaries may inject malicious code into processes."
    )

    assert isinstance(result[0].metadata, dict)
    assert "attack_code" in result[0].metadata
    assert "technic_name" in result[0].metadata
    assert "platforms" in result[0].metadata
    assert "tactics" in result[0].metadata

    assert result[0].metadata["attack_code"] == "T1055"
    assert result[0].metadata["technic_name"] == "Process Injection"
    assert result[0].metadata["platforms"] == ["windows"]

    assert isinstance(result[0].metadata["tactics"], list)
    assert "defense-evasion" in result[0].metadata["tactics"]
    assert "privilege-escalation" in result[0].metadata["tactics"]
    assert isinstance(result[0].metadata["platforms"], list)


def test_prepare_data_vectorization_do_not_crash():
    """Ensure splitting an empty result from parse_mitre_technics do not crash the entire program"""
    result = MitreParser.prepare_data_for_vectorization(
        MitreParser.parse_mitre_technics({})
    )

    assert isinstance(result, list)
    assert len(result) == 0
