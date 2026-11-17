from typing import Any


class StixCompiler:
    """
    Stateful Architectural Compilation component representing a single technique compilation context.
    Compile all extracted data into a single structured text block for LLM, and add a generic unique identifier.
    """

    def __init__(self, extracted_data: dict[str, Any]) -> None:
        self._stix_object = extracted_data

    def compile_fields(self) -> dict[str, Any]:
        """
        Main pipelines entry point step executed on the instance context.
        Enriches the input extracted data dictionary with semantic context without mutating it.
        """
        return {
            "id": self._stix_object[
                "mitre_id"
            ],  # <- because ingestion persistence client need a generic unique key.
            **self._stix_object,
            "compiled_text": self._compile_text(),
        }

    def _compile_text(self) -> str:
        """
        Generates the structured text block optimized for Transformer embedding engines.
        """
        compiled_chunks = []

        compiled_chunks.extend(
            [
                f"Technique ID: {self._stix_object['mitre_id']}",
                f"Technique Name: {self._stix_object['technic_name']}",
                f"Description: {self._stix_object['description']}",
            ]
        )

        # if stix object owns a "tactics" entry
        if self._stix_object.get("tactics", []):
            compiled_chunks.append(
                f"Tactics: {', '.join(self._stix_object['tactics'])}"
            )

        # if stix object owns a "platforms" entry
        if self._stix_object.get("platforms", []):
            compiled_chunks.append(
                f"Platforms: {', '.join(self._stix_object['platforms'])}"
            )

        # if stix object owns a "mutable-elements" entry
        if self._stix_object.get("mutable_elements", []):
            compiled_chunks.append("Mutable Detection Indicators:")
            for elem in self._stix_object["mutable_elements"]:
                compiled_chunks.append(f" - {elem['field']}: {elem['description']}")

        return "\n".join(compiled_chunks)
