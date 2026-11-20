# 🗄️ Persistence Module (`src/persistence/`)

The **`src/persistence/`** module provides a unified, storage-agnostic persistence layer engineered around **Interface
Segregation (ISP)**, **Abstract Factory**, and **Dependency Inversion**. In this implementation, a single **Redis**
server fulfills four distinct operational roles—JSON document storage, FIFO job queuing, read-only KNN vector search,
and incremental vector ingestion—through strictly isolated connection pools and specialized engine clients.

---

## 🏗️ Internal Component & Contract Architecture

```mermaid
flowchart TB
%% Styles
    classDef mgr fill: #334155, stroke: #94a3b8, color: #f8fafc, stroke-width: 1.5px
    classDef iface fill: #1e293b, stroke: #fbbf24, stroke-dasharray: 4 4, color: #fef3c7, stroke-width: 1.5px
    classDef factory fill: #451a03, stroke: #f59e0b, color: #f8fafc, stroke-width: 2px
    classDef client fill: #0f172a, stroke: #38bdf8, color: #f8fafc, stroke-width: 2px
    classDef driver fill: #3b0764, stroke: #c084fc, color: #f8fafc, stroke-width: 2px
    classDef guard fill: #064e3b, stroke: #10b981, color: #f8fafc, stroke-width: 1.5px
%% 1. Entry Point (Composition Root Only)
    subgraph Entry ["Composition Root Entry (src/startup/ Only)"]
        direction LR
        PM["PersistenceManager"]:::mgr
        PP["PersistenceProvider"]:::mgr
        PM --> PP
    end

%% 2. Segregated Public Contracts
    subgraph Interfaces ["Public Contracts (src/persistence/interfaces/)"]
        direction LR
        IFactory["IPersistenceFactory"]:::iface
        IJson["IJsonStorageEngine"]:::iface
        IQueue["IQueueEngine"]:::iface
        IVecSearch["IVectorSearchEngine"]:::iface
        IVecIngest["IVectorIngestionEngine"]:::iface
    end

%% 3. Concrete Redis Engine
    subgraph RedisEngine ["Redis Engine Implementation (src/persistence/engine/redis/)"]
        direction TB
        RFactory["RedisFactory\n(redis_factory.py)"]:::factory

        subgraph Clients ["Specialized Clients (One Isolated Pool per Client)"]
            direction LR
            CJson["JsonCacheClient\n(RESP3 • decode=True)"]:::client
            CQueue["RedisQueueClient\n(RESP3 • decode=True)"]:::client
            CVecSearch["VectorCacheClient\n(RESP2 • decode=False)"]:::client
            CVecIngest["IngestionCacheClient\n(RESP2 • decode=True)"]:::client
        end

        subgraph CoreDriver ["Driver & Mathematical Safety"]
            direction LR
            Driver["RedisDriver\n• ExponentialBackoff Retry\n• Auto RESP2/RESP3 Selection\n• YAML Schema Introspection\n• Non-blocking SCAN"]:::driver
            Specs["VectorFieldSpecs\n(dims, metric, algorithm)"]:::guard
            Guards["geometric_guards/geometry.py\n• is_distance_valid (IEEE 754)\n• clamp_distance_result [0..1]"]:::guard
        end

        RFactory -->|Instantiates| CJson
        RFactory -->|Instantiates| CQueue
        RFactory -->|Instantiates| CVecSearch
        RFactory -->|Instantiates| CVecIngest
        CJson --> Driver
        CQueue --> Driver
        CVecSearch --> Driver
        CVecIngest --> Driver
        Driver --> Specs
        CVecSearch --> Guards
    end

%% Wiring & Implementations
    PP -->|Resolves| IFactory
    RFactory -.->|Implements| IFactory
    CJson -.->|Implements| IJson
    CQueue -.->|Implements| IQueue
    CVecSearch -.->|Implements| IVecSearch
    CVecIngest -.->|Implements| IVecIngest
```

---

## 🧠 Key Engineering Decisions

### 1. Automatic RESP2 / RESP3 Protocol Negotiation (`RedisDriver`)

`RedisDriver` automatically selects the optimal wire protocol based on `vector_capability`:

* **RESP3 (`protocol=3`)** is enabled for `JsonCacheClient` and `RedisQueueClient` to leverage native Redis 7+
  structured responses.
* **RESP2 (`protocol=2`)** is enforced whenever `vector_capability=True` (`VectorCacheClient` and
  `IngestionCacheClient`). RediSearch (`FT.SEARCH`) in `redisvl==0.27.2` expects RESP2 `Result` objects exposing
  `.docs`; forcing RESP3 causes `redis-py` to return raw dictionaries and breaks `SearchIndex.query()`.
* **Strict Lifecycle Ownership (`owns_client=False`):** `SearchIndex.from_yaml()` is explicitly prevented from taking
  ownership of the underlying `Redis` client so `RedisDriver` retains deterministic control over connection pool
  creation and shutdown.

### 2. CQRS Split on Vector Operations (`VectorCacheClient` vs. `IngestionCacheClient`)

* **`VectorCacheClient` (`IVectorSearchEngine`, Read-Only Runtime):**
    * **Zero-Config Schema Introspection:** Reads vector dimensions, distance metrics, algorithms (`HNSW`/`FLAT`), and
      metadata field names directly from the RedisVL YAML schema at startup (`sync_lifespan_catalog`).
    * **Minimal Network Projection (`_resolve_return_fields`):** Intersects target Pydantic model fields with index
      metadata so heavy vector tensor blobs are never transferred back over the network during queries.
    * **DSL Isolation (`_build_tag_filter`):** Translates agnostic `dict[str, str]` filters into RedisVL `Tag(k) == v`
      AST expressions so domain layers never import `redisvl`.
    * **Geometric & IEEE 754 Guards:** Validates query vector dimensionality in $O(1)$ (`VectorDimensionMismatchError`),
      traps `NaN`/`Inf` distances (`is_distance_valid`), and normalizes raw metric distances into a `[0.0, 1.0]`
      similarity score (`clamp_distance_result`).
* **`IngestionCacheClient` (`IVectorIngestionEngine`, Ephemeral Boot Writer):**
    * **Delta-Sync via Semantic Fingerprints:** Uses atomic `HGETALL`/`HSET` operations on a dedicated hash registry
      (`_semantic_hashes_key`) so unchanged MITRE STIX documents are skipped—saving massive CPU cycles during startup.
    * **Flat Redis Hash Normalization (`_normalize_document_types`):** Packs float vectors into C-contiguous `float32`
      byte buffers via NumPy, joins Python lists into comma-delimited strings for Redis `TAG` fields, and serializes
      nested dicts to JSON strings.

### 3. Self-Pruning FIFO Queue (`RedisQueueClient`)

* Implements a strict FIFO queue using `LPUSH` (enqueue) and `RPOP` (dequeue), paired with a bounded completion list
  (`LPUSH` + `LTRIM` capped at `max_done_history`).
* **TTL-Aware Pipeline Pruning:** Because job records in `JsonCacheClient` carry a TTL, `get_pending()` and `get_done()`
  verify key existence in a single non-transaction Redis pipeline (`EXISTS`) and automatically prune expired job IDs
  (`LREM`) to prevent stale queue drift.

---

## 📋 Component Reference

| Component                                        | Contract                 | Protocol & Decoding   | Responsibility                                                                                        |
|:-------------------------------------------------|:-------------------------|:----------------------|:------------------------------------------------------------------------------------------------------|
| **`PersistenceManager` / `PersistenceProvider`** | `IPersistenceFactory`    | —                     | Factory resolution in `src/startup/` (never imported by business logic).                              |
| **`RedisDriver`**                                | —                        | RESP2 or RESP3        | Connection pooling, `ExponentialBackoff` retries, `SCAN` key iteration, and YAML index introspection. |
| **`JsonCacheClient`**                            | `IJsonStorageEngine`     | RESP3, `decode=True`  | CRUD operations (`JSON.GET`, `JSON.SET` at `$`) with automatic key `EXPIRE` TTL.                      |
| **`RedisQueueClient`**                           | `IQueueEngine`           | RESP3, `decode=True`  | FIFO job queue (`LPUSH`/`RPOP`), bounded completion history (`LTRIM`), and pipelined TTL pruning.     |
| **`VectorCacheClient`**                          | `IVectorSearchEngine`    | RESP2, `decode=False` | Read-only KNN similarity search, tag filtering, IEEE 754 distance clamping, and Pydantic hydration.   |
| **`IngestionCacheClient`**                       | `IVectorIngestionEngine` | RESP2, `decode=True`  | Bulk vector upsert (`search_index.load`), `float32` binary packing, and semantic hash delta tracking. |