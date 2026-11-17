import logging
from typing import Any

logger = logging.getLogger(__name__)


class StixFilter:
    """
    Architectural Guard component responsible for validating raw STIX 2.1 nodes.

    This filter ensures that only active, top-level Enterprise ATT&CK Techniques
    (attack-patterns) pass through the ingestion pipelines, systematically evicting
    deprecated data, and non-technical structural artifacts.
    """

    def __init__(self, stix_object: dict[str, Any]) -> None:
        self._stix_object = stix_object

    def is_valid_technique(self) -> bool:
        """
        Evaluates a raw STIX object's root properties against ingestion rules.

        The evaluation follows a strict short-circuit logical sequence:
        1. Node Type Validation (Must be an 'attack-pattern')
        2. Lifecycle Validation (Must NOT be revoked or deprecated)

        :return: True if we want to keep the stix object, False otherwise.
        """
        # Defensive check against corrupted or malformed non-dictionary payloads
        if not isinstance(self._stix_object, dict):
            logger.warning(
                f"Evicting STIX object: Invalid payload type. "
                f"Expected dict, got {type(self._stix_object).__name__}."
            )
            return False

        # Guard 1: Enforce structural object type boundary
        # Eliminates intrusion-sets (actors), malware, tools, and relationship components
        if self._stix_object.get("type") != "attack-pattern":
            return False

        # Guard 2: Enforce lifecycle and data lifecycle boundaries
        # Discards obsolete technical behaviors to prevent RAM bloat and historical false positives
        if (
            self._stix_object.get("revoked") is True
            or self._stix_object.get("deprecated") is True
        ):
            return False

        return True
