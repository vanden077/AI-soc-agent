# 🤖 LLM Inference Module (`src/llm/`)

The **`src/llm/`** module abstracts structured LLM inference behind a generic contract (`ILlmEngine[TLLMEngine]`),
ensuring the forensic domain (`SocAgent`) remains completely decoupled from Ollama, LangChain, or any specific model
runtime.

---

## 🏗️ Factory & Structured Inference Architecture

```mermaid
flowchart TB
%% Styles
    classDef boot fill: #334155, stroke: #94a3b8, color: #f8fafc, stroke-width: 1.5px
    classDef mgr fill: #451a03, stroke: #f59e0b, color: #f8fafc, stroke-width: 2px
    classDef iface fill: #1e293b, stroke: #fbbf24, stroke-dasharray: 4 4, color: #fef3c7, stroke-width: 1.5px
    classDef engine fill: #0f172a, stroke: #38bdf8, color: #f8fafc, stroke-width: 2px
    classDef domain fill: #3b0764, stroke: #c084fc, color: #f8fafc, stroke-width: 1.5px
%% Domain Consumer
    subgraph Consumer ["Forensic Domain Consumer (Interface-Only)"]
        Agent["SocAgent (src/soc_agent/agent.py)\n• Pass 1: analyze_event(prompt, GuardLayerVerdict)\n• Pass 2: analyze_event(prompt, ThreatAnalysis)"]:::domain
    end

%% Contract
    subgraph Contract ["Public Contract (interfaces/)"]
        ILLM["ILlmEngine[TLLMEngine]\n• analyze_event[T: BaseModel](prompt, response_schema) → T\n• _init_llm() → TLLMEngine\n• temperature = 0.0 (deterministic default)"]:::iface
    end

%% Composition Root Factory
    subgraph Factory ["Composition Root Factory (src/startup/ Only)"]
        direction LR
        LMgr["LlmManager\n• _ENGINE_REGISTRY lookup\n• importlib lazy dynamic loading"]:::mgr
        LProv["LlmProvider (StrEnum)\n• OLLAMA = 'ollama'"]:::boot
        LMgr --> LProv
    end

%% Concrete Engine
    subgraph Concrete ["Concrete Adapter (engine/ollama/)"]
        Ollama["OllamaEngine\n• ChatOllama.with_structured_output(T)\n• num_ctx=2048 | num_predict=110\n• keep_alive='10m' | Pydantic v2 validation"]:::engine
    end

    Agent --> ILLM
    LMgr -->|Instantiates & exposes| ILLM
    Ollama -.->|Implements| ILLM
```

---

## 🧠 Key Engineering Decisions

1. **Schema-Enforced Structured Output (`analyze_event[T: BaseModel]`):**
   Instead of parsing fragile free-form text with regular expressions, `ILlmEngine` accepts an arbitrary Pydantic v2
   `response_schema` (`GuardLayerVerdict` in Pass 1, `ThreatAnalysis` in Pass 2) and an agnostic `(role, content)`
   message list, enforcing strict schema validation before returning control to the domain layer.
2. **CPU & RAM Inference Tuning (`OllamaEngine`):**
   Configured specifically to deliver deterministic, low-latency inference on CPU-only hardware
   (`Intel Core i5-10210U`):
    * **`temperature=0.0`:** Maximizes reproducibility and deterministic forensic classification.
    * **`num_ctx=2048`:** Caps the KV-cache memory allocation and speeds up prompt evaluation on system RAM.
    * **`num_predict=110`:** Prevents local models from generating verbose prose or runaway tokens, keeping JSON
      responses tight and fast.
    * **`keep_alive="10m"`:** Retains model weights in RAM across consecutive alerts to eliminate cold-reload penalties
      while automatically reclaiming memory during idle periods.
3. **Lazy Dynamic Engine Resolution (`importlib.import_module`):**
   `LlmManager` resolves `LlmProvider` entries dynamically from `_ENGINE_REGISTRY`, ensuring alternative inference
   backends (e.g., Mistral, vLLM, OpenAI) can be added without loading unused client libraries at runtime.
4. **100% Unit Testability (`_init_llm()`):**
   Isolating `ChatOllama` instantiation inside `_init_llm()` provides a clean mocking boundary for testing
   `with_structured_output()` and `ValidationError` paths with 100% line and branch coverage.

---

## 📋 Component Reference

| Component                    | File                             | Responsibility                                                                                                |
|:-----------------------------|:---------------------------------|:--------------------------------------------------------------------------------------------------------------|
| **`ILlmEngine[TLLMEngine]`** | `interfaces/i_llm_engine.py`     | Generic abstract base class defining `analyze_event[T]`, `_init_llm`, and inference configuration properties. |
| **`LlmProvider`**            | `providers/llm_provider.py`      | `StrEnum` registry of supported LLM backends (`ollama`).                                                      |
| **`LlmManager`**             | `llm_manager.py`                 | Dynamic factory resolving provider strings into concrete `ILlmEngine` instances.                              |
| **`OllamaEngine`**           | `engine/ollama/ollama_engine.py` | Local Ollama adapter enforcing Pydantic v2 structured outputs with tuned CPU/RAM parameters.                  |