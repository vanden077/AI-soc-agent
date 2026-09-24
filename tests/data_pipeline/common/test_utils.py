import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from dataset_test import STIX_MOCK
from src.data_pipeline.common import utils
from src.data_pipeline.exceptions import MitreDownloadError, MitreJsonError


@pytest.fixture
def freeze_time_september_2026(monkeypatch):
    """Fixture to safely mock datetime.now() to Sept 22, 2026 while preserving fromisoformat."""

    def mock_now(tz=None):
        return datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)

    mock_datetime_class = type("MockDatetime", (datetime,), {"now": mock_now})
    monkeypatch.setattr("src.data_pipeline.common.utils.datetime", mock_datetime_class)


# ==========================================
# 1. FILE SYSTEM PROCESSING
# ==========================================


def test_check_matrix_is_locally_cached():
    """Should return True if the target JSON matrix file exists on the local file system."""
    with patch.object(Path, "exists", return_value=True):
        assert utils.check_matrix_is_locally_cached() is True


def test_create_local_matrix():
    """Should call mkdir with proper arguments to verify the cache folder structure creation."""
    with patch.object(Path, "mkdir") as mock_mkdir:
        utils.create_local_matrix()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ==========================================
# 2. DOWNLOAD STREAMS
# ==========================================


def test_download_latest_mitre_version_success():
    """Should execute the native Python download successfully when HTTP status is 200."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"objects": []}'

    m_open = mock_open()
    with (
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("urllib.request.Request") as mock_request_cls,
        patch("builtins.open", m_open),
    ):
        mock_urlopen.return_value.__enter__.return_value = mock_response
        utils.download_latest_mitre_version()

        mock_request_cls.assert_called_once()
        m_open.assert_called_once_with(Path(utils.MITRE_JSON_PATH), "wb")
        m_open().write.assert_called_once_with(b'{"objects": []}')


def test_download_latest_mitre_version_failure():
    """Should raise MitreDownloadError if the remote server returns a non-200 HTTP status code."""
    mock_response = MagicMock()
    mock_response.status = 404

    with (
        patch("urllib.request.urlopen") as mock_urlopen,
        pytest.raises(
            MitreDownloadError,
            match="Native cross-platform download sequence failed: MITRE server returned HTTP error code: 404",
        ),
    ):
        mock_urlopen.return_value.__enter__.return_value = mock_response
        utils.download_latest_mitre_version()


# ==========================================
# 3. METADATA AND DATE VALIDATIONS
# ==========================================


def test_get_mitre_file_modification_date_success():
    """Should correctly convert physical OS file timestamp into an ISO-8601 formatted string."""
    fixed_dt = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)

    with (
        patch("os.path.getmtime", return_value=fixed_dt.timestamp()),
        patch.object(Path, "exists", return_value=True),
    ):
        result = utils.get_mitre_file_modification_date()
        assert result == "2026-09-22T12:00:00Z"


def test_get_mitre_file_modification_date_missing_file():
    """Should raise FileNotFoundError when calling metadata extraction on a missing cache file."""
    with (
        patch.object(Path, "exists", return_value=False),
        pytest.raises(
            FileNotFoundError, match="Cannot extract metadata, file not found"
        ),
    ):
        utils.get_mitre_file_modification_date()


@pytest.mark.parametrize(
    "modified_str, expected_valid",
    [
        ("2026-09-21T12:00:00Z", True),
        ("2026-09-17T12:00:00.123Z", True),
        ("2026-09-17T11:59:59Z", False),
        ("2026-09-10T00:00:00+00:00", False),
    ],
)
def test_is_json_stix_up_to_date_cases(
    freeze_time_september_2026, modified_str: str, expected_valid: bool
):
    """Should enforce the strict 5-day cache TTL against the mocked time anchor."""
    assert utils._is_json_stix_up_to_date(modified_str) is expected_valid


@pytest.mark.parametrize("corrupted_str", ["malformed-date", ""])
def test_is_json_stix_up_to_date_corrupted(corrupted_str: str):
    """Should handle invalid or non-date string arguments gracefully by returning False."""
    assert utils._is_json_stix_up_to_date(corrupted_str) is False


def test_is_json_stix_up_to_date_naive_datetime(freeze_time_september_2026):
    """Should handle naive datetime strings by forcing UTC fallback inside the evaluation logic."""
    assert utils._is_json_stix_up_to_date("2026-09-20T12:00:00") is True


# ==========================================
# 4. JSON PARSING AND CACHE LOADING
# ==========================================


def test_find_mitre_collection_object_found():
    """Should successfully extract the unique x-mitre-collection block from the shared mock dataset."""
    result = utils._find_mitre_collection_object(STIX_MOCK)
    assert result is not None
    assert result["type"] == "x-mitre-collection"


def test_find_mitre_collection_object_missing():
    """Should return None if the x-mitre-collection block is manually removed from the payload."""
    stix_data = copy.deepcopy(STIX_MOCK)
    stix_data["objects"].pop(0)
    assert utils._find_mitre_collection_object(stix_data) is None


def test_load_json_mitre_missing_file():
    """Should return an empty dict gracefully if the target file cannot be found on disk."""
    with patch.object(Path, "exists", return_value=False):
        assert utils.load_json_mitre_in_memory() == {}


def test_load_json_mitre_invalid_json():
    """Should catch JSONDecodeError and wrap it into a MitreJsonError exception."""
    with (
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data="{ invalid json }")),
        pytest.raises(MitreJsonError, match="Invalid JSON structure detected in cache"),
    ):
        utils.load_json_mitre_in_memory()


def test_load_json_mitre_success(freeze_time_september_2026):
    """Should return the full parsed data structure if everything is valid and up to date based on OS metadata."""
    with (
        patch(
            "src.data_pipeline.common.utils.get_mitre_file_modification_date"
        ) as mock_mod_date,
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(STIX_MOCK))),
    ):
        mock_mod_date.return_value = "2026-09-21T12:00:00Z"
        assert utils.load_json_mitre_in_memory() == STIX_MOCK


def test_load_json_mitre_expired_cache(freeze_time_september_2026):
    """Should trigger a re-download indicator (empty dict) if OS file metadata shows it is older than 5 days."""
    with (
        patch(
            "src.data_pipeline.common.utils.get_mitre_file_modification_date"
        ) as mock_mod_date,
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(STIX_MOCK))),
    ):
        mock_mod_date.return_value = "2026-09-10T12:00:00Z"
        assert utils.load_json_mitre_in_memory() == {}


def test_load_json_mitre_missing_collection_object():
    """Should fallback and return empty dict if no collection metadata object is found in the stream."""
    invalid_payload = {
        "objects": [{"type": "attack-pattern", "id": "attack-pattern--1"}]
    }

    with (
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(invalid_payload))),
    ):
        assert utils.load_json_mitre_in_memory() == {}


def test_load_json_mitre_collection_missing_modified_key():
    """Should return an empty dict if the collection block exists but lacks its modification timestamp."""
    invalid_payload = {"objects": [{"type": "x-mitre-collection"}]}

    with (
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(invalid_payload))),
    ):
        assert utils.load_json_mitre_in_memory() == {}
