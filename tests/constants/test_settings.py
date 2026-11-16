from src.constants import Settings


def test_settings_mitre_full_stix_url_concatenates_base_url_and_release_tag(
    mock_settings: Settings,
) -> None:
    """Verify MITRE_FULL_STIX_URL builds the expected versioned STIX JSON URL."""
    custom_settings = mock_settings.model_copy(
        update={
            "MITRE_STIX_URL": "https://example.org",
            "MITRE_RELEASE_TAG": "19.2",
        }
    )

    assert custom_settings.MITRE_FULL_STIX_URL == "https://example.org19.2.json"