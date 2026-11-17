from src.data_pipeline.compilers.stix_compiler import StixCompiler


def test_stix_compiler_nominal_full_compilation():
    """
    GIVEN a complete STIX dataset including optional tactics, platforms, and nested mutable elements
    WHEN compiling fields via StixCompiler
    THEN verify all conditional blocks are correctly parsed, formatted and appended.
    """
    rich_data = {
        "mitre_id": "T1003.001",
        "technic_name": "LSASS Memory",
        "description": "Dumping memory from the lsass.exe process.",
        "parent_id": "T1003",
        "tactics": ["credential-access"],
        "platforms": ["Windows"],
        "mutable_elements": [
            {"field": "process", "description": "lsass.exe execution spikes"},
            {"field": "registry", "description": "SAM hive exfiltration tracks"},
        ],
    }

    compiler = StixCompiler(extracted_data=rich_data)
    result = compiler.compile_fields()

    # check generic id is added
    assert result["id"] == rich_data["mitre_id"]
    # check dict is not altered during compilation
    assert result["mitre_id"] == rich_data["mitre_id"]
    assert result["technic_name"] == rich_data["technic_name"]
    assert result["description"] == rich_data["description"]
    assert result["parent_id"] == rich_data["parent_id"]
    assert result["tactics"] == rich_data["tactics"]
    assert result["platforms"] == rich_data["platforms"]
    assert result["mutable_elements"] == rich_data["mutable_elements"]
    # check compiled text
    expected_text = (
        "Technique ID: T1003.001\n"
        "Technique Name: LSASS Memory\n"
        "Description: Dumping memory from the lsass.exe process.\n"
        "Tactics: credential-access\n"
        "Platforms: Windows\n"
        "Mutable Detection Indicators:\n"
        " - process: lsass.exe execution spikes\n"
        " - registry: SAM hive exfiltration tracks"
    )
    assert result["compiled_text"] == expected_text


def test_stix_compiler_robustness_with_empty_or_missing_fields():
    """
    GIVEN missing optional keys, empty lists, or None fields
    WHEN compiling fields via StixCompiler
    THEN verify the component defaults to empty structures safely without crashing and preserves input immutability.
    """
    dirty_data = {
        "mitre_id": "T1003",
        "technic_name": "OS Credential Dumping",
        "description": "Adversaries may dump credentials.",
        "parent_id": "",
        "tactics": [],  # Empty boundary
        "platforms": None,  # None type boundary
        # "mutable_elements" is completely missing to test dictionary fallback
    }
    original_data = dirty_data.copy()

    compiler = StixCompiler(extracted_data=dirty_data)
    result = compiler.compile_fields()

    # Assert immutability
    assert dirty_data == original_data
    assert result["id"] == "T1003"

    expected_text = (
        "Technique ID: T1003\n"
        "Technique Name: OS Credential Dumping\n"
        "Description: Adversaries may dump credentials."
    )
    assert result["compiled_text"] == expected_text
