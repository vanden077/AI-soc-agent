# 🧠 Pure Forensic AI Domain (`src/soc_agent/`)

The **`src/soc_agent/`** module encapsulates the core cybersecurity intelligence of **AI SOC Agent**. It contains zero
infrastructure drivers, database clients, or HTTP dependencies—communicating with the outside world strictly through
`ILlmEngine` and strongly-typed Pydantic v2 domain contracts.

---

## 🏗️ Domain Component Structure

```mermaid
flowchart LR
%% Styles
    classDef agent fill: #3b0764, stroke: #c084fc, color: #f8fafc, stroke-width: 2px
    classDef prompt fill: #0f172a, stroke: #38bdf8, color: #f8fafc, stroke-width: 2px
    classDef catalog fill: #451a03, stroke: #f59e0b, color: #f8fafc, stroke-width: 2px
    classDef schema fill: #064e3b, stroke: #10b981, color: #f8fafc, stroke-width: 1.5px
    classDef iface fill: #1e293b, stroke: #fbbf24, stroke-dasharray: 4 4, color: #fef3c7, stroke-width: 1.5px
    Agent["SocAgent\n(agent.py)"]:::agent
    PFactory["PromptFactory\n(prompt_factory/prompt_factory.py)"]:::prompt
    TCatalog["ThreatCatalog\n(threat_catalog/threat_catalog.py)"]:::catalog
    ILLM["ILlmEngine\n(src/llm/interfaces/)"]:::iface

    subgraph Schemas ["Domain Contracts (schemas/)"]
        direction TB
        S_Guard["GuardLayerVerdict\n• is_threat: bool\n• confidence_score: float [0..1]\n• semantic_summary: str | None (≤280 chars)"]:::schema
        S_Mitre["MitreTechnique\n• mitre_id & parent_id\n• technic_name, tactics, platforms\n• normalized_similarity [0..1] + __lt__"]:::schema
        S_Report["ThreatAnalysis\n• platform, is_threat, confidence_score\n• semantic_summary\n• matched_techniques: list[MitreTechnique]"]:::schema
    end

    Agent -->|Builds prompt| PFactory
    PFactory -->|Fetches platform rules| TCatalog
    Agent -->|Invokes structured inference| ILLM
    ILLM -.->|Validates & returns| S_Guard
    S_Report -->|Aggregates| S_Mitre
```

---

## 🧠 Key Engineering Decisions

1. **Anti-Paranoia Classification & Vocabulary Anchoring (`PromptFactory`):**
    * Enforces strict classification rules that explicitly whitelist routine administrative tasks, signed updaters, and
      expected background activity so SOC analysts are not flooded with false positives.
    * Instructs the LLM to rewrite suspicious events using canonical **MITRE ATT&CK terminology** (e.g., *Process
      Injection*, *OS Credential Dumping*, *Steal Application Access Token*) capped at 280 characters, aligning the
      query embedding space with `StixCompiler` index records.
    * Enforces `semantic_summary = null` on benign events to minimize CPU token generation overhead.
2. **11-Platform MITRE ATT&CK Enterprise v19.2 Registry (`ThreatCatalog`):**
   Maps every official STIX platform (`windows`, `macos`, `linux`, `pre`, `office suite`, `identity provider`, `saas`,
   `iaas`, `network devices`, `containers`, `esxi`) to platform-specific detection guidelines, preventing
   cross-ecosystem hallucinations.
3. **Strict Domain Contracts (`schemas/`):**
    * **`GuardLayerVerdict`:** Internal LLM-to-Workflow contract bounding `confidence_score` to `[0.0, 1.0]` and
      `semantic_summary` to `max_length=280`.
    * **`MitreTechnique`:** Represents a RedisVL candidate enriched with `parent_id` hierarchy and implements `__lt__`
      on `normalized_similarity` for clean native sorting.
    * **`ThreatAnalysis`:** Unified output schema guaranteed whether an event exits early as benign or completes full
      MITRE correlation.

---

## 📋 Component Reference

| Component               | File                               | Responsibility                                                                                   |
|:------------------------|:-----------------------------------|:-------------------------------------------------------------------------------------------------|
| **`SocAgent`**          | `agent.py`                         | Stateless forensic agent orchestrating prompt creation and structured `ILlmEngine` execution.    |
| **`PromptFactory`**     | `prompt_factory/prompt_factory.py` | Pure functional builder generating deterministic system/user message tuples.                     |
| **`ThreatCatalog`**     | `threat_catalog/threat_catalog.py` | Fail-fast registry of MITRE ATT&CK v19.2 detection guidelines across all 11 supported platforms. |
| **`GuardLayerVerdict`** | `schemas/first_guard_layer.py`     | Pydantic schema enforcing binary triage, calibrated confidence, and concise semantic summary.    |
| **`MitreTechnique`**    | `schemas/mitre_technique.py`       | Pydantic schema representing a scored MITRE ATT&CK technique or sub-technique (`parent_id`).     |
| **`ThreatAnalysis`**    | `schemas/threat_analysis.py`       | Final end-to-end forensic report contract returned by `SocAgentWorkflow`.                        |