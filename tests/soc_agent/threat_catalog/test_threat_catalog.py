import pytest

from src.soc_agent.threat_catalog import ThreatCatalog


@pytest.mark.parametrize(
    "platform",
    [
        "windows",
        "macos",
        "linux",
        "pre",
        "office suite",
        "identity provider",
        "saas",
        "iaas",
        "network devices",
        "containers",
        "esxi",
    ],
)
def test_get_guideline_returns_non_empty_mitre_guideline_for_known_platform(
    platform: str,
) -> None:
    """Nominal: retrieves the canonical MITRE guideline for every supported platform."""
    guideline = ThreatCatalog.get_guideline(platform)

    assert isinstance(guideline, str)
    assert guideline.startswith("Focus on MITRE mechanisms:")


def test_get_guideline_raises_key_error_on_unknown_platform() -> None:
    """Error: fails fast with KeyError when an unsupported platform key is passed."""
    with pytest.raises(KeyError):
        ThreatCatalog.get_guideline("unknown_platform")