import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class StixExtractor:
    """
    Architectural Extraction component responsible for isolating, parsing,
    and normalizing raw complex STIX 2.1 schemas into standard data dictionaries.
    """

    def __init__(self, stix_object: dict[str, Any]) -> None:
        self._stix_object = stix_object
        self._mitre_id: str = ""

    def extract_fields(self) -> dict[str, Any]:
        """
        Orchestrates the extraction and adaptation sequence of targeted STIX fields.

        :return: A standardized dictionary enriched with optional relationship context.
        """
        self._mitre_id = self._extract_mitre_id()

        extracted = {
            "mitre_id": self._mitre_id,
            "parent_id": self._extract_parent_id(),
            "technic_name": self._extract_technic_name(),
            "description": self._extract_description(),
            "platforms": self._extract_platforms(),
            "tactics": self._extract_tactics(),
            "mutable_elements": self._extract_mutable_elements(),
        }

        # compute semantic hash here, this way, if there is no upsert needed during pipeline
        # we don't have to compile object for persistence ingestion, we just skip it as soon as possible.
        extracted["semantic_hash"] = StixExtractor._compute_dict_hash(extracted)
        return extracted

    def _extract_mitre_id(self) -> str:
        """Extracts and validates the MITRE ATT&CK identifier syntax from external references."""
        external_references = self._stix_object.get("external_references", [])
        if isinstance(external_references, list):
            for ref in external_references:
                if ref.get("source_name") == "mitre-attack":
                    mitre_id = ref.get("external_id", "").strip()
                    if re.match(r"^T\d{4}(?:\.\d{3})?$", mitre_id):
                        return mitre_id
        raise ValueError(
            "Invalid STIX object: MITRE ID (format Txxxx or Txxxx.xxx) not found or malformed."
        )

    def _extract_parent_id(self) -> str:
        """
        Derives the parent technique identifier deterministically (e.g., T1055.001 -> T1055).
        Returns an empty string placeholder if the identifier represents a root technique.
        """
        if "." in self._mitre_id:
            return self._mitre_id.split(".")[0]
        return ""

    def _extract_technic_name(self) -> str:
        """Extracts and strictly validates the technique name."""
        technic_name = str(self._stix_object.get("name", "")).strip()

        if technic_name.lower() == "none":
            technic_name = ""

        if not technic_name:
            raise ValueError(
                f"Technique {self._mitre_id} is corrupted: 'name' field is missing or empty."
            )
        return technic_name

    def _extract_description(self) -> str:
        """Extracts and strictly validates the technique description text."""
        description = str(self._stix_object.get("description", "")).strip()

        if description.lower() == "none":
            description = ""

        if not description:
            raise ValueError(
                f"Technique {self._mitre_id} is corrupted: 'description' field is missing or empty."
            )
        return description

    def _extract_platforms(self) -> list[str]:
        """Extracts and sort the targeted execution platforms array."""
        mitre_platforms = self._stix_object.get("x_mitre_platforms", [])
        if not isinstance(mitre_platforms, list):
            return []

        platforms: list[str] = []
        for platform in mitre_platforms:
            platforms.append(str(platform))

        return sorted(platforms, key=StixExtractor._case_insensitive_sort_key)

    def _extract_tactics(self) -> list[str]:
        """Flattens, isolates and sort official 'mitre-attack' phase name labels."""
        phases = self._stix_object.get("kill_chain_phases", [])
        if not isinstance(phases, list):
            return []

        tactics: list[str] = []
        for phase in phases:
            if (
                isinstance(phase, dict)
                and phase.get("kill_chain_name") == "mitre-attack"
            ):
                phase_name = phase.get("phase_name")
                if phase_name:
                    tactics.append(str(phase_name))

        return sorted(tactics, key=StixExtractor._case_insensitive_sort_key)

    def _extract_mutable_elements(self) -> list[dict[str, str]]:
        """Extracts and sort telemetry-rich parameter fields crucial for system log semantic alignment."""
        elements = self._stix_object.get("x_mitre_mutable_elements", [])
        if not isinstance(elements, list):
            return []

        cleaned_elements: list[dict[str, str]] = []
        for elem in elements:
            if isinstance(elem, dict):
                field_name = elem.get("field")
                field_desc = elem.get("description")
                if field_name and field_desc:
                    cleaned_elements.append(
                        {"field": str(field_name), "description": str(field_desc)}
                    )

        return sorted(cleaned_elements, key=StixExtractor._serialize_for_sorting)

    # ============================================================================
    # PRIVATE UTILITY SORTING KEY METHODS
    # ============================================================================
    @staticmethod
    def _case_insensitive_sort_key(text_item: str) -> str:
        """Provides a lowercase transformation key for raw strings."""
        return str(text_item).lower()

    @staticmethod
    def _serialize_for_sorting(element: dict[str, str]) -> str:
        """Converts a dictionary element into a lowercase serialized JSON string."""
        return json.dumps(element, sort_keys=True, ensure_ascii=False).lower()

    @staticmethod
    def _compute_dict_hash(data: dict[str, Any]) -> str:
        """Computes a strict, deterministic SHA-256 fingerprint from a sorted JSON serialization."""
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
