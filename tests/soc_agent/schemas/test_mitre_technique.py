from src.soc_agent.schemas.mitre_technique import MitreTechnique


def _build_technique(mitre_id: str, similarity: float) -> MitreTechnique:
    return MitreTechnique(
        mitre_id=mitre_id,
        technic_name="Process Injection",
        tactics="Defense Evasion, Privilege Escalation",
        description="Adversaries may inject code into processes.",
        platforms="Windows, Linux",
        normalized_similarity=similarity,
    )


def test_mitre_technique_lt_compares_by_normalized_similarity() -> None:
    """Verify __lt__ compares two MitreTechnique instances by normalized_similarity."""
    low = _build_technique("T1055.001", 0.42)
    high = _build_technique("T1055", 0.89)

    assert (low < high) is True
    assert sorted([high, low]) == [low, high]