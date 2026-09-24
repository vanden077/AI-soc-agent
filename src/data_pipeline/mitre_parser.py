from typing import Any

from langchain_core.documents import Document


class MitreParser:
    @staticmethod
    def parse_mitre_technics(stix_json: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract all relevant and not deprecated MITRE technics including platforms and tactics.
        :return: list[dict[str, Any]]
        """
        technics: list[dict[str, Any]] = []
        for obj in stix_json.get("objects", []):
            if (
                obj.get("type") == "attack-pattern"
                and not obj.get("x_mitre_deprecated", False)
                and not obj.get("revoked", False)
            ):
                tech_id = ""
                for ref in obj.get("external_references", []):
                    if ref.get("source_name") == "mitre-attack":
                        tech_id = ref.get("external_id", "")
                        break

                if tech_id and obj.get("description"):
                    # Extract all tactics (kill_chain_phases)
                    tactics_list: list[str] = []
                    for phase in obj.get("kill_chain_phases", []):
                        if phase.get("kill_chain_name") == "mitre-attack" and phase.get(
                            "phase_name"
                        ):
                            tactics_list.append(phase["phase_name"])

                    technics.append(
                        {
                            "id": tech_id,
                            "name": obj.get("name", ""),
                            "description": obj.get("description", ""),
                            "platforms": obj.get("x_mitre_platforms", []),
                            "tactics": tactics_list,
                        }
                    )

        return technics

    @staticmethod
    def prepare_data_for_vectorization(
        mitre_technics: list[dict[str, Any]],
    ) -> list[Document]:
        """
        From parse_mitre_technics result, split data into content and metadata for Redis vectorization.
        :param mitre_technics: list[dict[str, Any]]
        :return: list[Document]
        """
        documents: list[Document] = []
        for technic in mitre_technics:
            content = f"Technic: {technic['name']} ({technic['id']}). Description: {technic['description']}"
            metadata = {
                "attack_code": technic["id"],
                "technic_name": technic["name"],
                "platforms": technic.get(
                    "platforms", []
                ),  # Embedded as list for metadata_schema mapping
                "tactics": technic["tactics"],
            }
            documents.append(Document(page_content=content, metadata=metadata))

        return documents
