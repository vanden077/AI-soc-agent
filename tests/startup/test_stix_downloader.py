import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from src.constants import Settings
from src.startup import download_stix_file


class _FakeHTTPResponse(BytesIO):
    """Minimal context-manager binary stream mimicking urllib HTTPResponse."""


def test_download_stix_file_skips_when_already_exists(
        mock_settings: Settings,
        tmp_path: Path,
) -> None:
    """Should skip download if the destination file already exists."""
    existing_file = tmp_path / "enterprise-attack.json"
    existing_file.write_bytes(b'{"type": "bundle"}')
    settings = mock_settings.model_copy(update={"MITRE_JSON_PATH": existing_file})

    with patch.object(urllib.request, "urlopen") as mock_urlopen:
        download_stix_file(settings)

    mock_urlopen.assert_not_called()
    assert existing_file.read_bytes() == b'{"type": "bundle"}'


def test_download_stix_file_downloads_atomically(
        mock_settings: Settings,
        tmp_path: Path,
) -> None:
    """Should create parent directories, stream chunks, set permissions, and atomically move the file."""
    target_file = tmp_path / "nested" / "dir" / "enterprise-attack.json"
    settings = mock_settings.model_copy(update={"MITRE_JSON_PATH": target_file})
    payload = b"A" * 70_000 + b"B" * 10_000

    with patch.object(
            urllib.request,
            "urlopen",
            return_value=_FakeHTTPResponse(payload),
    ) as mock_urlopen:
        download_stix_file(settings, timeout=15.0)

    mock_urlopen.assert_called_once_with(settings.MITRE_FULL_STIX_URL, timeout=15.0)
    assert target_file.is_file()
    assert target_file.read_bytes() == payload
    assert target_file.stat().st_mode & 0o777 == 0o644
    assert list(target_file.parent.iterdir()) == [target_file]


def test_download_stix_file_cleans_up_temp_file_on_error(
        mock_settings: Settings,
        tmp_path: Path,
) -> None:
    """Should remove the temporary file and re-raise if download fails."""
    target_file = tmp_path / "enterprise-attack.json"
    settings = mock_settings.model_copy(update={"MITRE_JSON_PATH": target_file})

    with (
        patch.object(
            urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ),
        pytest.raises(urllib.error.URLError, match="connection refused"),
    ):
        download_stix_file(settings)

    assert not target_file.exists()
    assert list(tmp_path.iterdir()) == []
