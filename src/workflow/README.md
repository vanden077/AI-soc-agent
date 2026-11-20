# 🔀 Forensic Workflow Orchestrator (`src/workflow/`)

The **`src/workflow/`** module orchestrates the end-to-end AI forensic pipeline via `SocAgentWorkflow`. Designed
specifically to achieve high accuracy and low latency on **CPU-only hardware**, it pairs a **single-pass Guard Layer LLM
inference** with **platform-filtered KNN vector retrieval** and **adaptive similarity clustering**.

---

## 🔄 Two-Stage Forensic Pipeline Flow

```mermaid
flowchart TB
%% Styles
    classDef input fill: #334155, stroke: #94a3b8, color: #f8fafc, stroke-width: 1.5px
    classDef llm fill: #3b0764, stroke: #c084fc, color: #f8fafc, stroke-width: 2px
    classDef gate fill: #451a03, stroke: #f59e0b, color: #f8fafc, stroke-width: 2px
    classDef vec fill: #0f172a, stroke: #38bdf8, color: #f8fafc, stroke-width: 2px
    classDef math fill: #064e3b, stroke: #10b981, color: #f8fafc, stroke-width: 2px
    classDef out fill: #1e293b, stroke: #fbbf24, color: #fef3c7, stroke-width: 1.5px
    Ingress(["Input: (platform: AvailablePlatforms, raw_log: str)"]):::input

    subgraph Stage1 ["Stage 1 — Single-Pass Guard Layer Triage & Semantic Translation"]
        Agent["SocAgent.analyze_ingress_flow(platform, raw_log)\n• Single structured LLM call (GuardLayerVerdict)\n• Translates noisy raw log into MITRE-aligned semantic_summary"]:::llm
        Gate{"verdict.is_threat\nAND\nverdict.semantic_summary?"}:::gate
        Benign(["Early Exit: ThreatAnalysis(\n is_threat=False,\n semantic_summary=None,\n matched_techniques=[]\n)\n(0 Embedding / 0 KNN I/O)"]):::out
        Agent --> Gate
        Gate -->|False: Nominal Activity| Benign
    end

    subgraph Stage2 ["Stage 2 — Platform-Filtered Vector RAG & Adaptive Clustering"]
        Embed["IEmbeddingEngine.embed_query(verdict.semantic_summary)\n• Embeds clean MITRE terminology instead of noisy log syntax"]:::vec
        KNN["IVectorSearchEngine.similarity_search(\n response_model=MitreTechnique,\n filter_expression={'platforms': platform.value},\n limit=5\n)"]:::vec
        Cluster["_filter_close_matches()\n• Sort DESC by normalized_similarity\n• Floor guard: top_score >= 0.45 (min_similarity)\n• Adaptive cluster cutoff: max(0.45, top_score - 0.035)"]:::math
        Report(["ThreatAnalysis(\n is_threat=True,\n confidence_score,\n semantic_summary,\n matched_techniques\n)"]):::out
        Embed --> KNN --> Cluster --> Report
    end

    Ingress --> Agent
    Gate -->|True: Threat Detected| Embed
```

---

## 🧠 Key Engineering Decisions

1. **Single-LLM-Call Architecture (Zero Second-Pass Generation Penalty):**
   Running two sequential LLM passes on a low-power CPU doubles latency. Instead, Stage 1 (`GuardLayerVerdict`) performs
   both **binary security triage** and **semantic query rewriting** in a single structured call—translating raw
   telemetry into a dense 20–35 word MITRE-aligned signature (`semantic_summary`). Stage 2 then resolves exact MITRE
   ATT&CK techniques deterministically via dense vector search without invoking the LLM a second time.
2. **Early Exit for Benign Telemetry:**
   If `is_threat` is `False`, `semantic_summary` is forced to `null` (saving output generation tokens) and the workflow
   returns immediately—bypassing neural query embedding and Redis KNN search completely.
3. **Ecosystem Isolation via Tag Pre-Filtering:**
   `similarity_search` passes `filter_expression={"platforms": platform.value}` so Windows logs are never matched
   against Linux-only or ESXi-only techniques.
4. **Adaptive Top-K Clustering (`_filter_close_matches`):**
   Rather than blindly returning all `knn_limit=5` neighbors (which often includes irrelevant tail matches), the
   workflow:
    * Discards all results if the best match falls below `min_similarity = 0.45`.
    * Retains only candidates within `similarity_delta = 0.035` of `top_score`, automatically returning 1 precise
      technique when a clear winner emerges or multiple closely clustered sub-techniques when behavior spans sibling
      mechanisms.