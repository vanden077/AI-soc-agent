import pytest
from pydantic import ValidationError
from src.api.schemas.log_ingress_payload import AvailablePlatforms, LogIngressPayload


@pytest.mark.parametrize(
    "raw_platform, expected_platform",
    [
        ("windows", AvailablePlatforms.WINDOWS),
        ("  WINDOWS  ", AvailablePlatforms.WINDOWS),
        ("office_suite", AvailablePlatforms.OFFICE_SUITE),
        ("office-suite", AvailablePlatforms.OFFICE_SUITE),
        ("  Identity-Provider_  ", AvailablePlatforms.IDENTITY_PROVIDER),
        ("Network   Devices", AvailablePlatforms.NETWORK_DEVICES),
    ],
)
def test_log_ingress_payload_normalizes_platform(
    raw_platform: str,
    expected_platform: AvailablePlatforms,
) -> None:
    """Verify normalize_platform trims whitespace, converts '-'/'_' to spaces, and lowercases."""
    payload = LogIngressPayload(
        platform=raw_platform,  # type: ignore[arg-type]
        raw_log="EventID=4688 NewProcessName=cmd.exe",
    )

    assert payload.platform is expected_platform


def test_log_ingress_payload_rejects_unknown_platform() -> None:
    """Verify invalid platform string fails Pydantic validation."""
    with pytest.raises(ValidationError):
        LogIngressPayload(
            platform="unknown_os",  # type: ignore[arg-type]
            raw_log="sample log",
        )


def test_log_ingress_payload_rejects_raw_log_exceeding_max_length() -> None:
    """Verify raw_log exceeding 12000 chars fails Pydantic max_length guard."""
    with pytest.raises(ValidationError):
        LogIngressPayload(
            platform=AvailablePlatforms.LINUX,
            raw_log="A" * 12001,
        )
