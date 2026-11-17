import re

import pytest
from src.data_pipeline.extractors.stix_extractor import StixExtractor

from tests.dataset_test import STIX_MOCK


def test_stix_extractor_nominal_root_technique():
    """
    Nominal Case: Extract and adapt an active root technique (T1055 Process Injection).
    Must verify that all dictionary keys match expected structures, lists are case-insensitively sorted,
    parent_id is an empty string placeholder, and semantic_hash is computed.
    """
    # Given: Index 0 is our valid root technique 'Process Injection'
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    # When
    extracted_data = extractor.extract_fields()

    # Then
    assert extracted_data["mitre_id"] == "T1055"
    assert extracted_data["parent_id"] == ""
    assert extracted_data["technic_name"] == "Process Injection"
    assert "Adversaries may inject malicious code" in extracted_data["description"]

    # Check case-insensitive sorted tags constraints
    assert extracted_data["platforms"] == ["Linux", "macOS", "Windows"]
    assert extracted_data["tactics"] == ["defense-evasion", "privilege-escalation"]

    # Check sorted nested mutable elements serialization constraint
    assert len(extracted_data["mutable_elements"]) == 1
    assert extracted_data["mutable_elements"][0]["field"] == "TargetProcessPath"

    # Ensure a strict deterministic SHA-256 fingerprint signature is present
    assert isinstance(extracted_data["semantic_hash"], str)
    assert len(extracted_data["semantic_hash"]) == 64


def test_stix_extractor_nominal_sub_technique():
    """
    Nominal Case: Extract an active sub-technique (T1055.001 DLL Injection).
    Must verify that parent_id correctly resolves to the parent technique (T1055) in O(1).
    """
    # Given: Index 1 is our valid sub-technique 'Dynamic Link Library Injection'
    stix_obj = STIX_MOCK["objects"][1]
    extractor = StixExtractor(stix_object=stix_obj)
    # When
    extracted_data = extractor.extract_fields()

    # Then
    assert extracted_data["mitre_id"] == "T1055.001"
    assert extracted_data["parent_id"] == "T1055"
    assert extracted_data["technic_name"] == "Dynamic Link Library Injection"
    assert extracted_data["platforms"] == ["Windows"]
    assert extracted_data["tactics"] == ["defense-evasion"]
    assert extracted_data["mutable_elements"] == []
    assert isinstance(extracted_data["semantic_hash"], str)
    assert len(extracted_data["semantic_hash"]) == 64


# ============================================================================
# 1. ISOLATED UNIT TESTS FOR _extract_mitre_id
# ============================================================================


def test_isolated_extract_mitre_id_root_success():
    """Should accurately parse a valid root technique ID from STIX_MOCK."""
    # STIX_MOCK["objects"][0] represents root technique T1055
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    assert extractor._extract_mitre_id() == "T1055"


def test_isolated_extract_mitre_id_sub_success():
    """Should accurately parse a valid sub-technique ID from STIX_MOCK."""
    # STIX_MOCK["objects"][1] represents sub-technique T1055.001
    stix_obj = STIX_MOCK["objects"][1]
    extractor = StixExtractor(stix_object=stix_obj)
    assert extractor._extract_mitre_id() == "T1055.001"


@pytest.mark.parametrize(
    "corrupted_id",
    [
        "INVALID-ID",  # Failed regex validation
        "T105",  # Malformed ID length (short)
        "T1055.01",  # Malformed sub-technique digits (must be 3 digits)
        "   ",  # Empty string or whitespaces
    ],
)
def test_isolated_extract_mitre_id_raises_on_invalid_format(corrupted_id):
    """Should strictly reject any MITRE ID pattern mismatch with a ValueError."""
    obj = {
        "external_references": [
            {"source_name": "mitre-attack", "external_id": corrupted_id}
        ]
    }
    extractor = StixExtractor(stix_object=obj)

    expected_msg = "Invalid STIX object: MITRE ID (format Txxxx or Txxxx.xxx) not found or malformed."
    with pytest.raises(ValueError, match=re.escape(expected_msg)):
        extractor._extract_mitre_id()


def test_isolated_extract_mitre_id_raises_on_empty_references():
    """Should raise a ValueError if external_references block is entirely missing or null."""
    obj = {"external_references": None}
    extractor = StixExtractor(stix_object=obj)

    expected_msg = "Invalid STIX object: MITRE ID (format Txxxx or Txxxx.xxx) not found or malformed."
    with pytest.raises(ValueError, match=re.escape(expected_msg)):
        extractor._extract_mitre_id()


# ============================================================================
# 2. ISOLATED UNIT TESTS FOR _extract_parent_id TOPOLOGY POINTER
# ============================================================================


def test_isolated_extract_parent_id_from_sub_technique():
    """Should resolve the correct parent root technique ID when processing a sub-technique."""
    stix_obj = STIX_MOCK["objects"][1]
    extractor = StixExtractor(stix_object=stix_obj)
    # Manually hydrate mitre_id
    extractor._mitre_id = extractor._extract_mitre_id()
    assert extractor._extract_parent_id() == "T1055"


def test_isolated_extract_parent_id_from_root_technique():
    """Should return an empty string placeholder when processing an already root technique."""
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    # Manually hydrate mitre_id
    extractor._mitre_id = extractor._extract_mitre_id()
    assert extractor._extract_parent_id() == ""


# ============================================================================
# 3. ISOLATED UNIT TESTS FOR TECHNICAL TEXT STRIPPING (_extract_technic_name & _extract_description)
# ============================================================================


def test_isolated_extract_technic_name_success():
    """Should return the clean technical name text from STIX_MOCK."""
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    assert extractor._extract_technic_name() == "Process Injection"


def test_isolated_extract_description_success():
    """Should capture the rich metadata description paragraph from STIX_MOCK."""
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    assert (
        "Adversaries may inject malicious code into processes"
        in extractor._extract_description()
    )


@pytest.mark.parametrize("corrupted_name", [None, "", "    "])
def test_isolated_extract_technic_name_raises_on_empty(corrupted_name):
    """Should trigger a Fail-Fast ValueError if the text name property is corrupted."""
    obj = {"name": corrupted_name}
    extractor = StixExtractor(stix_object=obj)
    extractor._mitre_id = "T1055"  # Hydrate context for logging contract

    with pytest.raises(
        ValueError,
        match="Technique T1055 is corrupted: 'name' field is missing or empty",
    ):
        extractor._extract_technic_name()


@pytest.mark.parametrize("corrupted_desc", [None, "", "    "])
def test_isolated_extract_description_raises_on_empty(corrupted_desc):
    """Should trigger a Fail-Fast ValueError if the text description property is corrupted."""
    obj = {"description": corrupted_desc}
    extractor = StixExtractor(stix_object=obj)
    extractor._mitre_id = "T1055"  # Hydrate context for logging contract

    with pytest.raises(
        ValueError,
        match="Technique T1055 is corrupted: 'description' field is missing or empty",
    ):
        extractor._extract_description()


# ============================================================================
# 4. ISOLATED UNIT TESTS FOR _extract_platforms
# ============================================================================


def test_isolated_extract_platforms_sorting_and_casing():
    """Should sort execution platforms arrays case-insensitively using STIX_MOCK data."""
    # STIX_MOCK contains ["Windows", "Linux", "macOS"]
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    # Must enforce strict case-insensitive alphabetical sorting array output
    assert extractor._extract_platforms() == ["Linux", "macOS", "Windows"]


@pytest.mark.parametrize(
    "corrupted_payload",
    [
        {"x_mitre_platforms": "invalid_string_instead_of_list"},
        {"x_mitre_platforms": 12345},
        {"x_mitre_platforms": None},
    ],
)
def test_isolated_extract_platforms_fallback_on_malformed_type(corrupted_payload):
    """Should safely fallback to an empty list if x_mitre_platforms is not a list primitive."""
    extractor = StixExtractor(stix_object=corrupted_payload)
    assert extractor._extract_platforms() == []


# ============================================================================
# 5. ISOLATED UNIT TESTS FOR _extract_tactics
# ============================================================================


def test_isolated_extract_tactics_filtering_and_sorting():
    """Should filter out non-mitre phases and return sorted threat phase names."""
    # STIX_MOCK contains "defense-evasion" and "privilege-escalation"
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    assert extractor._extract_tactics() == ["defense-evasion", "privilege-escalation"]


@pytest.mark.parametrize(
    "corrupted_payload",
    [
        {"kill_chain_phases": "corrupted_string_payload"},
        {"kill_chain_phases": {"invalid": "dictionary"}},
        {"kill_chain_phases": None},
    ],
)
def test_isolated_extract_tactics_fallback_on_malformed_type(corrupted_payload):
    """Should safely fallback to an empty list if kill_chain_phases is not a list primitive."""
    extractor = StixExtractor(stix_object=corrupted_payload)
    assert extractor._extract_tactics() == []


# ============================================================================
# 6. ISOLATED UNIT TESTS FOR COMPLEX PARAMETERS (_extract_mutable_elements)
# ============================================================================


def test_isolated_extract_mutable_elements_validation_and_sorting():
    """Should parse telemetry parameters array and sort them based on serialized strings."""
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)
    result = extractor._extract_mutable_elements()

    assert len(result) == 1
    assert result[0]["field"] == "TargetProcessPath"
    assert "memory-tampered" in result[0]["description"]


@pytest.mark.parametrize(
    "corrupted_payload",
    [
        {"x_mitre_mutable_elements": "invalid_telemetry_string"},
        {"x_mitre_mutable_elements": 99.99},
        {"x_mitre_mutable_elements": None},
    ],
)
def test_isolated_extract_mutable_elements_fallback_on_malformed_type(
    corrupted_payload,
):
    """Should safely fallback to an empty list if x_mitre_mutable_elements is not a list primitive."""
    extractor = StixExtractor(stix_object=corrupted_payload)
    assert extractor._extract_mutable_elements() == []


# ============================================================================
# 7. DETERMINISTIC HASH FINGERPRINTS
# ============================================================================


def test_static_compute_dict_hash_determinism_on_real_records():
    """Verify that dictionary payload serialization guarantees fingerprint stability."""
    stix_obj = STIX_MOCK["objects"][0]
    extractor = StixExtractor(stix_object=stix_obj)

    extracted_a = extractor.extract_fields()

    # Forcing a shallow dictionary permutation to test json.dumps(sort_keys=True)
    permuted_keys_dict = {k: v for k, v in reversed(list(extracted_a.items()))}

    hash_a = StixExtractor._compute_dict_hash(extracted_a)
    hash_b = StixExtractor._compute_dict_hash(permuted_keys_dict)

    assert hash_a == hash_b
    assert len(hash_a) == 64
