import json
import logging
import os
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from ..exceptions import MitreDownloadError, MitreJsonError

logger = logging.getLogger(__name__)
# Note: following should be env vars, but it's just a PoC
MITRE_STIX_URL: Final[str] = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
)
MITRE_JSON_PATH: Final[Path] = Path("data/mitre/enterprise-attack.json")
REDIS_URL: Final[str] = "redis://localhost:6379/0"
INDEX_NAME: Final[str] = "mitre_attack_v1"


def check_matrix_is_locally_cached() -> bool:
    """Check if the MITRE attack JSON file exists on the local file system."""
    return MITRE_JSON_PATH.exists()


def create_local_matrix() -> None:
    """Ensure the directory tree for the MITRE matrix cache exists."""
    MITRE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)


def download_latest_mitre_version() -> None:
    """
    Downloads the freshest STIX matrix from the official MITRE repository.
    Injects professional browser headers to bypass firewalls and prevent HTML fallback.
    Guarantees cross-platform execution (Windows/Linux/Mac) within the host venv.
    """
    logger.info(
        f"Downloading freshest MITRE matrix via native Python layer from {MITRE_STIX_URL}"
    )

    destination_path = Path(MITRE_JSON_PATH)

    # 1. Define strict headers to force JSON content type and bypass robot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        req = urllib.request.Request(MITRE_STIX_URL, headers=headers)

        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise MitreDownloadError(
                    f"MITRE server returned HTTP error code: {response.status}"
                )

            with open(destination_path, "wb") as f:
                f.write(response.read())

        logger.info(f"[+] MITRE matrix successfully cached at: {destination_path}")

    except Exception as err:
        raise MitreDownloadError(
            f"Native cross-platform download sequence failed: {str(err)}"
        ) from err


def load_json_mitre_in_memory() -> dict[str, Any]:
    """
    Check MITRE JSON is valid and not out to date.
    Sometimes redirections are not correctly followed and returns HTML.
    We need a valid JSON to complete the process.
    Everything is done in the same function because we don't want to load multiple times
    a file weighting more than 50Mo from disk.
    :raises: MitreJsonError
    :return: JSON as dict
    """
    if not MITRE_JSON_PATH.exists():
        return {}

    with open(MITRE_JSON_PATH, "r", encoding="utf-8") as f:
        try:
            stix_data = json.load(f)
        except json.JSONDecodeError as err:
            raise MitreJsonError(
                f"Invalid JSON structure detected in cache: {err}"
            ) from err

    # Secured extraction of metadata
    collection_obj = _find_mitre_collection_object(stix_data)
    if not collection_obj or "modified" not in collection_obj:
        logger.warning(
            "Could not find a valid x-mitre-collection object or modification timestamp in JSON."
        )
        return {}

    if not _is_json_stix_up_to_date(get_mitre_file_modification_date()):
        logger.info(
            "Local MITRE matrix cache is older than 5 days. Forcing re-download."
        )
        return {}

    return stix_data


def _find_mitre_collection_object(stix_data: dict[str, Any]) -> dict[str, Any] | None:
    """Scan the STIX objects array to find the global x-mitre-collection metadata block."""
    for obj in stix_data.get("objects", []):
        if obj.get("type") == "x-mitre-collection":
            return obj
    return None


def get_mitre_file_modification_date() -> str:
    """
    Extracts the physical file modification date from the local OS cache.
    Returns an ISO formatted string to match the delta calculation inputs.
    """
    file_path = Path(MITRE_JSON_PATH)
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot extract metadata, file not found: {file_path}")

    # Get the timestamp from the OS metadata
    timestamp = os.path.getmtime(file_path)

    # Convert to ISO format string (e.g., '202UTC2:47Z')
    dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_json_stix_up_to_date(last_modified_str: str) -> bool:
    """Compare the collection modification date against the current time.

    Returns True if the file is less than 5 days old.
    """
    try:
        # Replace 'Z' suffix by '+00:00' for timezone-aware guarantee
        clean_timestamp = last_modified_str.replace("Z", "+00:00")
        last_modified_dt = datetime.fromisoformat(clean_timestamp)

        # Force UTC comparison
        if last_modified_dt.tzinfo is None:
            last_modified_dt = last_modified_dt.replace(tzinfo=UTC)

        expiration_limit = datetime.now(UTC) - timedelta(days=5)
        return last_modified_dt >= expiration_limit

    except (ValueError, TypeError) as err:
        logger.error(
            f"Failed to parse MITRE modification date '{last_modified_str}': {err}"
        )
        return False
