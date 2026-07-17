# TrinaxAI Architecture

## High-Level Overview

```
LAN browser ── HTTPS ──► PWA gateway :3334 ──► allowlisted Ollama chat
                         └─ paired token ─────► RAG/private capabilities
                                                     │
                          signed peer/method/path HMAC│ allowlisted model calls
                                                     ▼
Local CLI ───────────────────────────────► FastAPI :3333 ──► Ollama :11434
                                            loopback          loopback
                                               │
                                               └──► LlamaIndex · vector + BM25
```

TrinaxAI is a **three-tier local stack**:

1. **PWA Frontend** (React 19 + TypeScript + Vite) on port 3334
2. **RAG API** (FastAPI + LlamaIndex) on loopback port 3333
3. **Ollama** (model runtime) on loopback port 11434

The PWA gateway on 3334 is the LAN-facing boundary. It forwards to the two
loopback services, signs the verified original peer for FastAPI and exposes only
the Ollama operations the UI needs. Inference and persisted data run on the host
by default. Installing dependencies/models, opt-in research and configured
external endpoints can use the network.

---

## Component Architecture

### `config.py` — Central Configuration Hub

The single source of truth for all subsystems. Defines:

- **Model fleet** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP`, and `MODEL_FAST`; their concrete names come from the active profile and can be overridden in `.env`.
- **Hardware profiles** — auto-tuned by `TRINAXAI_PROFILE` (4gb/8gb/16gb/max/ultra)
- **Embedding presets** — bge-m3 balanced, nomic lite, all-minilm fast
- **Factory functions** — `make_llm()`, `make_embed()`, `make_reranker()`
- **Auto-router** — `route_model()` heuristic classifier (no LLM call needed)
- **File rules** — what to index, what to skip, chunk sizes per profile

### `app/` — Modular FastAPI Backend

`app/main.py` owns application creation, middleware, exception handlers and
lifespan initialization. `app/routes/` defines the HTTP layer, `app/schemas/`
owns validation contracts, and `app/services/` contains focused domain logic.
`app/services/engine_state.py` is the only mutable engine-state source.
`rag_api.py` is only a backward-compatible launcher/facade.

Key subsystems:

| Feature | Implementation |
|---|---|
| **Hybrid retrieval** | Vector (bge-m3) + BM25 (keyword) → reciprocal rank fusion |
| **Reranking** | Optional cross-encoder (bge-reranker-v2-m3) reorders candidates when enabled |
| **Collections** | Separate namespaces within the same vector store |
| **Project detection** | Heuristic from file paths and user query |
| **Memory** | Typed facts/preferences/decisions/notes with provenance and expiry; each turn retrieves only relevant active entries |
| **Research** | Multi-pass local/web retrieval; bounded page reads expose `full_page` or `snippet_only` provenance |
| **Device pairing** | Single-use codes issue revocable bearer capabilities with explicit scopes; only keyed hashes persist |
| **File watcher** | watchdogs file system for auto-reindexing |
| **Rate limiting** | Monotonic token bucket per verified IP/bucket; capacity 30 and full refill over 60 s by default |
| **Usage stats** | JSONL-based local analytics |
| **App state sync** | Schema-v2 operations with explicit deletes, server revision, ETag/CAS and conflict merge |

### `index.py` — Document Indexer

- **File collection** — Aggressive directory pruning skips `node_modules`, `.git`, `venv`, etc.
- **AST-aware chunking** — `CodeSplitter` for 15+ languages, `SentenceSplitter` for prose
- **Incremental mode** — Content fingerprints include BLAKE2b-256 plus extractor/chunker/embedding pipeline versions
- **Multi-source collections** — Each independently synchronized root has a stable `source_id`; the same relative path may exist in several roots
- **Crash-safe publication** — Index files and manifest stage together, publish under a durable journal/generation marker, and roll back after an interrupted commit
- **Collection support** — Each chunk carries `collection_id`, `source_id`, relative path and provenance metadata

### `chat-pwa/` — React PWA Frontend

TypeScript components built with Tailwind CSS and framer-motion include:

| Component | Purpose |
|---|---|
| `ChatInterface` | Main chat UI with streaming, markdown, voice, slash commands |
| `ChatSidebar` | Session history, folders, search, and export workflows |
| `Settings` | Local model, indexing, prompt, memory, and statistics controls |
| `KnowledgeBrowser` | Explore indexed chunks by collection→file→chunk |
| `Sources` | Citation cards with file, project, snippet, score |
| `OnboardingWizard` | First-time profile and model setup |
| `Docs` | Bilingual in-app user documentation |

**Tech stack**: React 19, Vite 6, TypeScript, Tailwind CSS, vite-plugin-pwa, react-markdown

### `trinaxai_cli/` — Terminal Interface

Python package with subcommands including `chat`, `agent`, `index`, `browse`,
`research`, `memory`, `collections`, `watch`, `export`, `obsidian`, `pair`, and
`doctor`.

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
  ├─ Docs attached? → store attachment reference; extract bounded text for this turn
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
            → model lifecycle follows the configured keep_alive value
```

---

## Indexing Flow

```
index.py starts
  │
  ├─ collect_files(root) → os.walk with aggressive pruning
  │
  ├─ SourceContext(root, collection_id, source_id)
  │
  ├─ current_state(paths) → content + pipeline fingerprints
  │
  ├─ read_manifest() → canonicalized key map (collection:source:path)
  │
  ├─ Diff: new_files, changed, deleted
  │
  ├─ load_docs(paths) → Document objects with metadata
  │
  ├─ build_nodes(docs) → CodeSplitter (AST) or SentenceSplitter
  │
  ├─ Embed nodes (bge-m3, no LLM needed)
  │
  └─ stage index + manifest → journaled publish → generation marker
```

---

## Security Model

| Layer | Mechanism |
|---|---|
| **Network** | FastAPI and Ollama loopback by default; PWA gateway is the only LAN-facing service |
| **Gateway identity** | Client peer/method/path signed with fresh HMAC; backend ignores ordinary forwarding headers |
| **Device identity** | Single-use pairing; `chat,read_private` by default; scoped, revocable bearer token retained only for the browser session |
| **Protected endpoints** | Direct loopback, matching device scope, or administrator super-credential; invalid supplied credentials fail closed |
| **Ollama facade** | Explicit method/path allowlist, peer authorization, monotonic token bucket and shared inference lock |
| **Agent** | Registered workspace roots; path/symlink enforcement; networkless Linux bubblewrap; fail closed without isolation |
| **TLS** | Managed services can use local certificates; `TRINAXAI_TLS_VERIFY` controls selected outgoing verification |
| **Sudoers** | Optional exact command points to a root-owned lifecycle wrapper, never repository-editable scripts |
| **Data** | Host-backed by default; web search, model/dependency downloads and configured remote endpoints are explicit network paths |

---

## Storage Layout

```
storage/
├── docstore.json          # LlamaIndex document store
├── index_store.json       # LlamaIndex index metadata
├── *_vector_store.json    # Persisted vector stores/namespaces
├── graph_store.json       # LlamaIndex graph store
├── manifest.json          # Source/path→content + pipeline fingerprints
├── .index-generation.json # Durable active-generation commit marker
├── .proxy_secret          # Private gateway/backend HMAC key
├── .device_secret         # Private key for device-token/code hashes
├── device_pairing.json    # Scoped devices and code/token keyed hashes
├── collections.json       # Collection metadata
├── usage.jsonl            # Usage statistics (JSON lines)
├── app_state.json         # Schema-v2 values + monotonic server revision
├── chat_attachments/      # Host-backed synchronized chat files
├── usage_summary.json     # Cached usage aggregate
└── user_memory*.json      # Memory entries/summary when present
```

---

## Key Design Decisions

- **No LLM during indexing** — only embeddings, saves RAM
- **AST chunking** — respects function/class boundaries for code
- **Hybrid search** — vector + BM25 fusion catches both semantic and exact matches
- **Heuristic auto-routing** — no LLM call, instant and free
- **Collections** — first-class concept throughout the stack
- **PWA over Electron** — lighter, phone-friendly, no native toolchain
- **Transactional incremental index** — content/pipeline fingerprints plus one
  cross-process writer lock and recoverable generation publication
- **Explicit multi-source identity** — `source_id` prevents one root from
  replacing or deleting another root's namesake files
- **Versioned browser sync** — localStorage remains the client store, while
  server revisions, operations and explicit deletes prevent blind snapshot overwrite
- **Scoped device pairing** — a short local/admin-authorized ceremony issues a
  revocable capability without distributing the administrator secret

---

## Contributor Guide: Where to Touch What

This section helps contributors find the right files for common tasks.

### Chat / Conversational AI

| What to change | Where |
|---|---|
| Chat endpoint logic | `app/routes/chat.py` + `app/services/rag_service.py` |
| RAG retrieval + synthesis | `app/services/rag_service.py` (`run_rag`, `build_engine`, `prepare_query`) |
| SSE streaming | `app/services/rag_service.py` `generate_stream()` + `chat-pwa/src/lib/api.ts` |
| Prompt template | `app/generation/prompts.py` (`GROUNDED_QA_TEMPLATE`) |
| Model auto-routing | `config.py` `route_model()` |
| Frontend chat UI | `chat-pwa/src/components/ChatInterface.tsx` |
| Frontend streaming hook | `chat-pwa/src/hooks/useStreamChat.ts` |

### Indexing / RAG Pipeline

| What to change | Where |
|---|---|
| Document indexing | `index.py` (entry point), `config.py` (chunking settings) |
| Chunking strategy | `index.py` — `CodeSplitter` for code, `SentenceSplitter` for prose |
| Embeddings model | `config.py` `make_embed()` |
| Incremental indexing | `index.py` manifest logic + `config.py` `MANIFEST_PATH` |
| Transaction publication/recovery | `trinaxai_index_storage.py` |
| Index upload (browser folder) | `app/routes/system.py` + `app/services/system_service.py` |
| File watcher | `app/services/watcher_service.py` + `app/routes/watcher.py` |

### Memory System

| What to change | Where |
|---|---|
| Memory CRUD | `app/services/memory_service.py` |
| Memory summary (LLM) | `app/services/memory_service.py` `_memory_refresh_sync()` |
| Relevant turn memory | `POST /v1/memory/context` + `app/services/memory_service.py::memory_context_for_query()`; delimited as untrusted data |
| Frontend memory panel | `chat-pwa/src/components/MemoryPanel.tsx` |

### Knowledge Collections

| What to change | Where |
|---|---|
| Collection CRUD | `app/services/collection_service.py` |
| Collection endpoints | `app/routes/collections.py` |
| Collection-based retrieval filter | `app/services/rag_service.py` `_cached_retrieve()` |
| Frontend collection UI | `chat-pwa/src/components/KnowledgeBrowser.tsx` |

### CLI

| What to change | Where |
|---|---|
| CLI entry point | `trinaxai_cli/app.py` |
| Individual subcommands | `trinaxai_cli/commands/*.py` |
| CLI config | `trinaxai_cli/config.py` |
| CLI session management | `trinaxai_cli/session.py` |
| Shared helpers | `trinaxai_core.py` |

### Installers

| What to change | Where |
|---|---|
| Linux/macOS install | `install.sh` |
| Windows install (PowerShell) | `install.ps1` |
| Update | `update.sh` / `update.ps1` |
| Uninstall | `uninstall.sh` / `uninstall.ps1` |
| Service management | `service_manager.py` + `startup_ai.sh` / `shutdown_ai.sh` |
| Hardware profile setup | `install_ollama_16gb_profile.sh` |

---

## Running Tests

### Backend (Python)

```bash
# All backend tests
.venv/bin/python -m pytest -q

# Specific test files
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
.venv/bin/python -m pytest tests/test_rag_api_reset_and_sources.py -v

# Deterministic metric tests and a live/saved-result golden evaluation
.venv/bin/python -m pytest tests/test_rag_metrics.py -v
.venv/bin/python scripts/evaluate_rag.py --api-url https://localhost:3333 \
  --token "$TRINAXAI_ADMIN_TOKEN" --output rag-eval-report.json

# Lint
.venv/bin/python -m ruff check .

# Type checking (best-effort, not strict)
.venv/bin/python -m py_compile rag_api.py config.py index.py
```

### Frontend (TypeScript/React)

```bash
cd chat-pwa
npx vitest run              # Unit tests
npx tsc --noEmit            # Type checking
npm run build               # Production build check
```

### Pre-release Audit

```bash
python3 scripts/public_readiness.py
```

### Makefile Shortcuts

```bash
make test        # Backend + frontend tests
make lint        # Ruff + TypeScript typecheck
make check       # Lint + test + audit + build
make audit       # Blocking local audits
```

---

## Security-Sensitive Zones

These areas require extra care when modifying:

| Zone | Risk | Mitigation |
|---|---|---|
| `/system/*` endpoints | Process control (startup, shutdown, reload) | Canonical guard: `app/security/admin_auth.py::authorize_system` |
| `/system/index-upload` | File system writes | Path traversal prevention, size limits, sanitized names |
| `_factory_reset_runtime_state` | Data deletion | Confirmation header required, only clears `storage/` and `local_sources/` |
| `authorize_system` | Access control bypass | Keep the single implementation in `app/security/admin_auth.py` covered by endpoint tests |
| CORS configuration | Cross-origin access | Default: localhost + LAN only; configurable via `TRINAXAI_CORS_ORIGINS` |
| `_spawn_service_manager` | Subprocess execution | Only predefined actions, detached process |
| PWA `/api/rag` proxy | Remote-to-loopback privilege confusion | Strip client identity and attach a fresh HMAC-signed original peer |
| PWA `/api/ollama` proxy | Model/disk administration and scheduler bypass | Fixed allowlist, remote credential, monotonic token bucket and inference lock |
| Device pairing registry | Token theft, replay and over-broad access | Single-use expiring codes, keyed hashes, mode-0600 atomic files, scopes and revocation |
| Agent shell | Host access and process escape | Registered roots, bubblewrap without network, process-group kill, fail closed |
| Rate limiting | DoS protection | Monotonic token bucket per verified IP/bucket, capacity 30 with 60 s refill by default |

---

## How LAN Authorization Works

1. The gateway removes client-supplied forwarding/TrinaxAI identity headers,
   verifies the remote device/admin credential, and signs the verified peer,
   method, path and freshness data for its loopback FastAPI request.
2. FastAPI accepts that assertion only from loopback with the shared HMAC key;
   stale, replayed, malformed or path-mismatched assertions fail closed.
3. A real direct-loopback caller has local operator privilege. A valid admin
   token has every scope. A paired token receives only its recorded scopes.
4. Each route asks for its concrete scope: `chat`, `read_private`, `index`,
   `system`, or `agent`. A supplied but invalid credential is never ignored.
5. The legacy private-LAN fallback applies only to system control when explicitly
   enabled and no admin token exists. All other unmatched requests return `403`.
6. `agent_yolo` never enables remote HTTP auto-approval; remote dangerous tools
   always require an approval decision.

**Defaults:**
- `TRINAXAI_ADMIN_TOKEN` — empty (not set). Localhost access works automatically.
- Device pairing grants `chat,read_private` unless the host explicitly requests
  more scopes. The clear token is returned once and held in PWA `sessionStorage`.
- `TRINAXAI_ALLOW_LAN_SYSTEM` — `0`; the legacy system-control fallback remains
  disabled. Prefer pairing and keep the admin super-credential on the host.

**Testing the security model:**
```bash
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
```

---

## Project Principles

These principles guide all design and contribution decisions:

1. **Local-first** — Local inference and host-backed storage are the default. Network use still occurs for installation/model downloads and any endpoints a user configures remotely.
2. **Privacy by default** — Chat data, indexed code, and documents are stored locally by default. There are no built-in accounts; local usage metrics remain on the host.
3. **No mandatory cloud** — Ollama runs locally. Optional: users can point to a remote Ollama instance on their own infrastructure.
4. **Confirmations for dangerous actions** — Factory reset, collection deletion, and system shutdown require explicit confirmation headers or interactive prompts.
5. **Security by default** — Backends bind to loopback, LAN capabilities require
   scoped pairing, the legacy LAN fallback is disabled, and CORS remains only an
   additional browser control rather than identity.
6. **Backward compatibility** — `rag_api.py` remains a thin compatibility facade; new code uses `app.main`, routers and services directly.
7. **Cross-platform with evidence** — Linux is CI-tested on Ubuntu. Windows and macOS have installers plus CI syntax/smoke validation, but full end-to-end OS validation must remain explicit.
8. **Accessible** — Spanish and English bilingual support. PWA works on mobile. CLI works over SSH.
9. **Small, focused PRs** — Prefer small, well-tested changes over large refactors. Each PR should address one concern.
10. **Documentation lives with code** — Architecture decisions are documented here, with dedicated API, CLI, configuration, PWA, and developer references.

---

## Related Documents

- [Documentation index](README.md) — Complete guide and reference map
- [API Reference](API_REFERENCE.md) — HTTP contracts and endpoints
- [Configuration Reference](CONFIGURATION.md) — Variables, profiles, and security
- [CLI Reference](CLI_REFERENCE.md) — Commands, flags, and TOML
- [Developer Guide](DEVELOPER_GUIDE.md) — Local setup, conventions, debugging
- [PWA Documentation](../chat-pwa/README.md) — Frontend runtime and development
- [Security Policy](../SECURITY.md) — Threat model and reporting
- [Contributing Guide](../CONTRIBUTING.md) — PR process and guidelines
