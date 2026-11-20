# 🧬 Embedding Module (`src/embedding/`)

The **`src/embedding/`** module abstracts dense vector generation behind a generic contract
(`IEmbeddingEngine[EmbEngine]`), decoupling both the startup STIX ETL pipeline (`StixPipeline`) and the runtime forensic
workflow (`SocAgentWorkflow`) from any specific neural embedding runtime.

---

## 🏗️ Factory & Dependency Inversion Architecture

```mermaid
flowchart TB
%% Styles
    classDef boot fill: #334155, stroke: #94a3b8, color: #f8fafc, stroke-width: 1.5px
    classDef mgr fill: #451a03, stroke: #f59e0b, color: #f8fafc, stroke-width: 2px
    classDef iface fill: #1e293b, stroke: #fbbf24, stroke-dasharray: 4 4, color: #fef3c7, stroke-width: 1.5px
    classDef engine fill: #0f172a, stroke: #38bdf8, color: #f8fafc, stroke-width: 2px
    classDef consumer fill: #064e3b, stroke: #10b981, color: #f8fafc, stroke-width: 1.5px
%% Consumers
    subgraph Consumers ["Downstream Consumers (Interface-Only)"]
        direction LR
        C_ETL["StixPipeline\nembed_documents(batch)"]:::consumer
        C_WF["SocAgentWorkflow\nembed_query(text)"]:::consumer
    end

%% Contract
    subgraph Contract ["Public Contract (interfaces/)"]
        IEmb["IEmbeddingEngine[EmbEngine]\n• embed_query(text: str) → list[float]\n• embed_documents(texts: list[str]) → list[list[float]]\n• _init_embedding() → EmbEngine"]:::iface
    end

%% Composition Root Factory
    subgraph Factory ["Composition Root Factory (src/startup/ Only)"]
        direction LR
        EMgr["EmbeddingManager\n• _ENGINE_REGISTRY lookup\n• importlib lazy dynamic loading"]:::mgr
        EProv["EmbeddingProvider (StrEnum)\n• HUGGINGFACE = 'huggingface'"]:::boot
        EMgr --> EProv
    end

%% Concrete Engine
    subgraph Concrete ["Concrete Adapter (engine/huggingface/)"]
        HF["HuggingFaceEngine\n• Wraps HuggingFaceEmbeddings\n• Native SIMD/AVX batching"]:::engine
    end

    C_ETL --> IEmb
    C_WF --> IEmb
    EMgr -->|Instantiates & exposes| IEmb
    HF -.->|Implements| IEmb
```

---

## 🧠 Key Engineering Decisions

1. **Lazy Dynamic Engine Resolution (`importlib.import_module`):**
   `EmbeddingManager` maps `EmbeddingProvider` enum keys to dotted module paths inside `_ENGINE_REGISTRY` and
   dynamically imports only the active engine class at startup. Adding alternative providers (e.g., OpenAI, ONNX, or
   local APIs) never loads unused SDK dependencies into memory.
2. **Workload-Segregated Embedding Methods:**
    * **`embed_documents(texts)`:** Optimized for high-throughput batch vectorization during MITRE STIX ingestion
      (`StixPipeline`), leveraging native SentenceTransformers/PyTorch SIMD and AVX CPU vector instructions.
    * **`embed_query(text)`:** Optimized for low-latency single-log vectorization during live forensic analysis
      (`SocAgentWorkflow`).
3. **100% Unit Testability by Design (`_init_embedding()`):**
   Model loading is isolated inside `_init_embedding()` rather than inline in `__init__()`, allowing unit tests to mock
   model initialization cleanly without triggering local weight downloads or PyTorch allocations.

---

## 📋 Component Reference

| Component                         | File                                       | Responsibility                                                                                         |
|:----------------------------------|:-------------------------------------------|:-------------------------------------------------------------------------------------------------------|
| **`IEmbeddingEngine[EmbEngine]`** | `interfaces/i_embedding_engine.py`         | Generic abstract base class defining `embed_query`, `embed_documents`, and engine metadata properties. |
| **`EmbeddingProvider`**           | `providers/embedding_provider.py`          | `StrEnum` registry of supported embedding backends (`huggingface`).                                    |
| **`EmbeddingManager`**            | `embedding_manager.py`                     | Dynamic factory resolving provider strings into concrete `IEmbeddingEngine` instances.                 |
| **`HuggingFaceEngine`**           | `engine/huggingface/huggingface_engine.py` | Local SentenceTransformers adapter executing CPU-friendly dense embeddings.                            |