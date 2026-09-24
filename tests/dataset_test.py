from typing import Any

"""Be careful if you need to update those data during tests, 
make a local deep_copy instead of updating directly those dict."""

# _________ MITRE ATTACK CORRELATION (schema) _________
MITRE_ATTACK_CORRELATION_SCHEMA: dict[str, Any] = {
    "tactic": "Credential Access",
    "technic_id": "T1003.001",
    "technic_name": "LSASS Memory",
    "confidence_score": 5,
}

# _________ EVENT ANALYSIS (schema) _________
EVENT_ANALYSIS_SCHEMA: dict[str, Any] = {
    "is_threat": True,
    "revised_severity": "CRITICAL",
    "justification": "Detected LSASS dumping via PowerShell arguments.",
    "mitre_correlations": [],
    "suggested_action": "ISOLATE_HOST",
}

# _________ SIEM ALERT STATE (model) _________
SIEM_ALERT_STATE_MODEL: dict[str, Any] = {
    "raw_alert": {"id": "SYS-99"},
    "correlated_logs": [
        {"test1": "something that is a string"},
        {"test2": 1},
        {"test3": []},
    ],
    "analysis": None,
    "metadata": {},
}

# _________ MITRE PIPELINE _________
STIX_MOCK: dict[str, Any] = {
    "type": "bundle",
    "id": "bundle--mock-id",
    "spec_version": "2.1",
    "objects": [
        {
            "type": "x-mitre-collection",
            "id": "x-mitre-collection--1f5f1533-f617-4ca8-9ab4-6a02367b81f9",
            "name": "Enterprise ATT&CK",
            "modified": "2026-09-20T12:00:00.000Z",
            "spec_version": "2.1",
        },
        {
            "id": "attack-pattern--valid-1",
            "type": "attack-pattern",
            "name": "Process Injection",
            "description": "Adversaries may inject malicious code into processes.",
            "x_mitre_deprecated": False,
            "x_mitre_platforms": ["windows"],
            "revoked": False,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1055"}
            ],
            "kill_chain_phases": [
                {
                    "kill_chain_name": "mitre-attack",
                    "phase_name": "defense-evasion",
                },
                {
                    "kill_chain_name": "mitre-attack",
                    "phase_name": "privilege-escalation",
                },
            ],
        },
        {
            "id": "attack-pattern--deprecated-2",
            "type": "attack-pattern",
            "name": "Obsolete Technic",
            "description": "Deprecated method.",
            "x_mitre_deprecated": True,
            "x_mitre_platforms": ["windows", "linux"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1000"}
            ],
        },
        {
            "id": "attack-pattern--revoked-3",
            "type": "attack-pattern",
            "name": "Obsolete Technic",
            "description": "Deprecated method.",
            "x_mitre_deprecated": False,
            "x_mitre_platforms": [],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1000"}
            ],
            "revoked": True,
        },
        {"id": "identity--mitre", "type": "identity", "name": "MITRE Corporation"},
    ],
}
