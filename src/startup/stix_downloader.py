import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from src.constants import Settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65_536


def download_stix_file(settings: Settings, timeout: float = 30.0) -> None:
    """Idempotently and atomically download the MITRE STIX JSON file if missing."""
    destination = settings.MITRE_JSON_PATH
    if destination.is_file():
        logger.info(
            "[STIX DOWNLOADER] File already exists at '%s', skipping download.",
            destination,
        )
        return

    url = settings.MITRE_FULL_STIX_URL
    logger.info("[STIX DOWNLOADER] Downloading MITRE STIX dataset from '%s'...", url)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, raw_tmp_path = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    tmp_path = Path(raw_tmp_path)

    try:
        with (
            tmp_path.open("wb") as tmp_file,
            urllib.request.urlopen(url, timeout=timeout) as response,
        ):
            while chunk := response.read(_CHUNK_SIZE):
                tmp_file.write(chunk)

        tmp_path.chmod(0o644)
        tmp_path.replace(destination)
        logger.info(
            "[STIX DOWNLOADER] Dataset successfully saved to '%s'.", destination
        )

    except Exception as exc:
        logger.error("[STIX DOWNLOADER] Failed to download MITRE STIX file: %s", exc)
        tmp_path.unlink(missing_ok=True)
        raise
