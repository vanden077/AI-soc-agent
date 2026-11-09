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
"""
Static immutable test datasets mimicking real MITRE ATT&CK STIX 2.1 schemas (v19.2/v20).
Declared as a constant module layer to optimize memory layout and test suite execution speed.
"""
STIX_MOCK: dict[str, Any] = {
  "type": "bundle",
  "id": "bundle--mock-fixture-19-2",
  "objects": [
    {
      "type": "attack-pattern",
      "id": "attack-pattern--0c8ab3fa-df48-4b9c-ace7-beacaac81cc5",
      "name": "Process Injection",
      "description": "Adversaries may inject malicious code into processes to evade defenses.",
      "x_mitre_platforms": ["Windows", "Linux", "macOS"],
      "x_mitre_is_subtechnique": False,
      "deprecated": False,
      "revoked": False,
      "x_mitre_mutable_elements": [
        {
          "field": "TargetProcessPath",
          "description": "The destination binaries being memory-tampered."
        }
      ],
      "kill_chain_phases": [
        {
          "kill_chain_name": "mitre-attack",
          "phase_name": "defense-evasion"
        },
        {
          "kill_chain_name": "mitre-attack",
          "phase_name": "privilege-escalation"
        }
      ],
      "external_references": [
        {
          "source_name": "mitre-attack",
          "external_id": "T1055"
        }
      ]
    },
    {
      "type": "attack-pattern",
      "id": "attack-pattern--3fc01293-ef5e-41c6-86ce-61f10706b64a",
      "name": "Dynamic Link Library Injection",
      "description": "Adversaries may inject dynamic link libraries into processes.",
      "x_mitre_platforms": ["Windows"],
      "x_mitre_is_subtechnique": True,
      "deprecated": False,
      "revoked": False,
      "kill_chain_phases": [
        {
          "kill_chain_name": "mitre-attack",
          "phase_name": "defense-evasion"
        }
      ],
      "external_references": [
        {
          "source_name": "mitre-attack",
          "external_id": "T1055.001"
        }
      ]
    },
    {
      "type": "attack-pattern",
      "id": "attack-pattern--6fa224c7-5091-4595-bf15-3fc9fe2f2c7c",
      "name": "Automated Collection (Legacy)",
      "description": "Adversaries may alter execution parameters to collect data automatically.",
      "x_mitre_platforms": ["Windows", "Linux"],
      "x_mitre_is_subtechnique": False,
      "deprecated": True,
      "revoked": False,
      "kill_chain_phases": [
        {
          "kill_chain_name": "mitre-attack",
          "phase_name": "collection"
        }
      ],
      "external_references": [
        {
          "source_name": "mitre-attack",
          "external_id": "T1119"
        }
      ]
    },
    {
      "type": "attack-pattern",
      "id": "attack-pattern--75b9a4d2-d4e2-4ca1-9aab-1badd9e05fd0",
      "name": "Hooking (Obsolete Key)",
      "description": "Adversaries may use hooking to redirect execution flows.",
      "x_mitre_platforms": ["Windows"],
      "x_mitre_is_subtechnique": False,
      "deprecated": False,
      "revoked": True,
      "kill_chain_phases": [
        {
          "kill_chain_name": "mitre-attack",
          "phase_name": "persistence"
        }
      ],
      "external_references": [
        {
          "source_name": "mitre-attack",
          "external_id": "T1179"
        }
      ]
    },
    {
      "type": "intrusion-set",
      "id": "intrusion-set--00f67a77-86a4-4adf-be26-1a54fc713340",
      "name": "APT28",
      "description": "APT28 is a threat group that has been active since at least 2004.",
      "aliases": ["Fancy Bear", "SNAKEMETH"]
    }
  ]
}
