# TrinaxAI Architecture

## High-Level Overview

```
┌──────────────────────────────────────────┐
│              Your Device                 │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │PWA(React)│  │ VSCode (Continue)   │   │
│  │  :3334   │  │ continue-config.yaml│   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │    RAG API (FastAPI) :3333         │   │
│  │ LlamaIndex · bge-m3 · BM25        │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │   Ollama   │  qwen2.5 · llama3.2       │
│  │   :11434   │  bge-m3 · moondream       │
│  └────────────┘                            │
└──────────────────────────────────────────┘
```

TrinaxAI is a **three-tier local stack**:

1. **PWA Frontend** (React 19 + TypeScript + Vite) on port 3334
2. **RAG API** (FastAPI + LlamaIndex) on port 3333
3. **Ollama** (model runtime) on port 11434

Everything runs on localhost or a trusted private LAN. No cloud dependencies.

---

## Component Architecture

### `config.py` — Central Configuration Hub

The single source of truth for all subsystems. Defines:

- **Model fleet** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP`, `MODEL_FAST`
- **Hardware profiles** — auto-tuned by `TRINAXAI_PROFILE` (8gb/16gb/max/ultra)
- **Embedding presets** — bge-m3 balanced, nomic lite, all-minilm fast
- **Factory functions** — `make_llm()`, `make_embed()`, `make_reranker()`
- **Auto-router** — `route_model()` heuristic classifier (no LLM call needed)
- **File rules** — what to index, what to skip, chunk sizes per profile

### `rag_api.py` — FastAPI Backend (2000+ lines)

The heart of the system. Key subsystems:

| Feature | Implementation |
|---|---|
| **Hybrid retrieval** | Vector (bge-m3) + BM25 (keyword) → reciprocal rank fusion |
| **Reranking** | Cross-encoder (bge-reranker-v2-m3) reorders candidates |
| **Collections** | Separate namespaces within the same vector store |
| **Project detection** | Heuristic from file paths and user query |
| **Memory** | Explicit "remember that" facts stored and auto-summarized |
| **Deep research** | Multi-pass decomposition with sub-question RAG |
| **File watcher** | watchdogs file system for auto-reindexing |
| **Rate limiting** | Token bucket, 30 req/min per IP, thread-safe |
| **Usage stats** | JSONL-based local analytics |
| **App state sync** | Cross-device shared key-value store |

### `index.py` — Document Indexer

- **File collection** — Aggressive directory pruning skips `node_modules`, `.git`, `venv`, etc.
- **AST-aware chunking** — `CodeSplitter` for 15+ languages, `SentenceSplitter` for prose
- **Incremental mode** — Manifest tracks file→mtime, only re-indexes changed/new files
- **Collection support** — Each chunk tagged with `collection_id` metadata
- **Output** — LlamaIndex `VectorStoreIndex` persisted to `storage/`

### `chat-pwa/` — React PWA Frontend

18 components in TypeScript with Tailwind CSS and framer-motion:

| Component | Purpose |
|---|---|
| `ChatInterface` | Main chat UI with streaming, markdown, voice, slash commands |
| `ChatSidebar` | Session history, search, export (Markdown/PDF/Word) |
| `Settings` | 5-section config panel (general, indexing, prompts, memory, stats) |
| `KnowledgeBrowser` | Explore indexed chunks by collection→file→chunk |
| `Sources` | Citation cards with file, project, snippet, score |
| `OnboardingWizard` | 7-step first-time setup |
| `Docs` | 11-section in-app documentation |

**Tech stack**: React 19, Vite 6, TypeScript, Tailwind CSS, vite-plugin-pwa, react-markdown

### `trinaxai_cli/` — Terminal Interface

Python package with subcommands: `chat`, `index`, `browse`, `research`, `memory`, `collections`, `watch`, `export`, `obsidian`, `doctor`.

Uses `httpx` for API calls and `rich` for terminal formatting.

### `service_manager.py` — Cross-Platform Supervisor

Abstracts service lifecycle across OSes:
- **Linux**: systemd with subprocess fallback
- **macOS**: launchctl with subprocess fallback
- **Windows**: Direct subprocess + `--watch` auto-restart loop

---

## Chat Data Flow

```
User types query in PWA
  │
  ├─ Slash command? → built-in handler (e.g., /index, /memory)
  ├─ Image attached? → routeVisionModel() → streamOllamaVision()
  ├─ Docs attached? → extractDocumentText() → inject into prompt
  │
  └─ Normal text:
       │
       ├─ RAG engine:
       │    POST /v1/chat/completions → FastAPI
       │    │
       │    ├─ route_model(query) → picks best Ollama model (heuristic)
       │    ├─ prepare_query() → enriches with previous user turn
       │    ├─ _fusion_retriever.retrieve() → hybrid vector+BM25 search
       │    ├─ detect_project() → filters by mentioned project
       │    ├─ collections filter → narrows to active collections
       │    ├─ reranker → reorders by cross-encoder relevance
       │    ├─ get_response_synthesizer().synthesize() → LLM with context
       │    └─ SSE stream + source citations → back to PWA
       │
       └─ Ollama engine:
            routeOllamaModel() → Ollama /api/chat (JSON lines)
            → model unload (keep_alive=0)
```

---

## Indexing Flow

```
index.py starts
  │
  ├─ collect_files(root) → os.walk with aggressive pruning
  │
  ├─ current_state(paths) → {source_key: mtime}
  │
  ├─ read_manifest() → canonicalized key map (collection:path → mtime)
  │
  ├─ Diff: new_files, changed, deleted
  │
  ├─ load_docs(paths) → Document objects with metadata
  │
  ├─ build_nodes(docs) → CodeSplitter (AST) or SentenceSplitter
  │
  ├─ Embed nodes (bge-m3, no LLM needed)
  │
  └─ persist to storage/ + write_manifest()
```

---

## Security Model

| Layer | Mechanism |
|---|---|
| **Network** | Localhost + private LAN only (CORS filter by IP + port) |
| **System endpoints** | Require localhost/LAN or admin token (`TRINAXAI_ADMIN_TOKEN`) |
| **LAN control** | `TRINAXAI_ALLOW_LAN_SYSTEM=0` disables LAN system access |
| **TLS** | HTTPS with self-signed certs (localhost-only, `TRINAXAI_TLS_VERIFY` controls) |
| **Sudoers** | `setup_trinaxai.sh` creates `/etc/sudoers.d/trinaxai` for service control |
| **Data** | All data stays on device — no cloud uploads, no telemetry |

---

## Storage Layout

```
storage/
├── docstore.json          # LlamaIndex document store
├── index_store.json       # FAISS/vector index
├── manifest.json          # File→mtime for incremental indexing
├── collections.json       # Collection metadata
├── usage.jsonl            # Usage statistics (JSON lines)
└── app_state.json         # Cross-device shared state
```

---

## Key Design Decisions

- **No LLM during indexing** — only embeddings, saves RAM
- **AST chunking** — respects function/class boundaries for code
- **Hybrid search** — vector + BM25 fusion catches both semantic and exact matches
- **Heuristic auto-routing** — no LLM call, instant and free
- **Collections** — first-class concept throughout the stack
- **PWA over Electron** — lighter, phone-friendly, no native toolchain
- **Incremental everything** — manifest-based change detection, seconds not hours
- **localStorage as primary store** — with backup, compaction, and cross-device sync
