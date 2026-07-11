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
│  │   Ollama   │  qwen3 · qwen2.5-coder    │
│  │   :11434   │  bge-m3 · qwen3-vl        │
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

- **Model fleet** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP`, `MODEL_FAST` (all tool-calling capable and non-thinking, i.e. agent-ready)
- **Hardware profiles** — auto-tuned by `TRINAXAI_PROFILE` (4gb/8gb/16gb/max/ultra)
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

TypeScript components built with Tailwind CSS and framer-motion include:

| Component | Purpose |
|---|---|
| `ChatInterface` | Main chat UI with streaming, markdown, voice, slash commands |
| `ChatSidebar` | Session history, folders, search, and export workflows |
| `Settings` | 5-section config panel (general, indexing, prompts, memory, stats) |
| `KnowledgeBrowser` | Explore indexed chunks by collection→file→chunk |
| `Sources` | Citation cards with file, project, snippet, score |
| `OnboardingWizard` | First-time profile and model setup |
| `Docs` | Bilingual in-app user documentation |

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
            → model lifecycle follows the configured keep_alive value
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
| **Network** | Configurable bind address plus explicit CORS origins/regex |
| **Protected endpoints** | Require loopback, opted-in private LAN, or admin token (`TRINAXAI_ADMIN_TOKEN`) |
| **LAN control** | `TRINAXAI_ALLOW_LAN_SYSTEM=0` disables LAN system access |
| **TLS** | Managed services can use local certificates; `TRINAXAI_TLS_VERIFY` controls selected outgoing verification |
| **Sudoers** | `setup_trinaxai.sh` creates `/etc/sudoers.d/trinaxai` for service control |
| **Data** | All data stays on device — no cloud uploads, no telemetry |

---

## Storage Layout

```
storage/
├── docstore.json          # LlamaIndex document store
├── index_store.json       # LlamaIndex index metadata
├── *_vector_store.json    # Persisted vector stores/namespaces
├── graph_store.json       # LlamaIndex graph store
├── manifest.json          # File→mtime for incremental indexing
├── collections.json       # Collection metadata
├── usage.jsonl            # Usage statistics (JSON lines)
├── app_state.json         # Cross-device shared state
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
- **Incremental everything** — manifest-based change detection, seconds not hours
- **localStorage as primary store** — with backup, compaction, and cross-device sync

---

## Contributor Guide: Where to Touch What

This section helps contributors find the right files for common tasks.

### Chat / Conversational AI

| What to change | Where |
|---|---|
| Chat endpoint logic | `rag_api.py` → `/v1/chat/completions` — migrating to `app/routes/chat.py` |
| RAG retrieval + synthesis | `app/services/rag_service.py` (`run_rag`, `build_engine`, `prepare_query`) |
| SSE streaming | `rag_api.py` `generate_stream()` + `chat-pwa/src/lib/api.ts` `parseRagSseLine()` |
| Prompt template | `app/services/rag_service.py` `qa_prompt_tmpl` |
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
| Index upload (browser folder) | `rag_api.py` `/system/index-upload` |
| File watcher | `rag_api.py` `_watch_Handler` class + `/v1/watch/*` endpoints |

### Memory System

| What to change | Where |
|---|---|
| Memory CRUD | `app/services/memory_service.py` |
| Memory summary (LLM) | `app/services/memory_service.py` `memory_refresh()` |
| Memory injection in chat | `rag_api.py` context injection in prompt chain |
| Frontend memory panel | `chat-pwa/src/components/MemoryPanel.tsx` |

### Knowledge Collections

| What to change | Where |
|---|---|
| Collection CRUD | `app/services/collection_service.py` |
| Collection endpoints | `rag_api.py` `/collections/*` — migrating to `app/routes/collections.py` |
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
| `/system/*` endpoints | Process control (startup, shutdown, reload) | Runtime guard is `rag_api.py::_authorize_system`; extracted `app/security/admin_auth.py` must stay in sync until route migration completes |
| `/system/index-upload` | File system writes | Path traversal prevention, size limits, sanitized names |
| `_factory_reset_runtime_state` | Data deletion | Confirmation header required, only clears `storage/` and `local_sources/` |
| `_authorize_system` / `authorize_system` | Access control bypass | Keep runtime and extracted auth logic behavior equivalent during migration |
| CORS configuration | Cross-origin access | Default: localhost + LAN only; configurable via `TRINAXAI_CORS_ORIGINS` |
| `_spawn_service_manager` | Subprocess execution | Only predefined actions, detached process |
| Rate limiting | DoS protection | Token bucket per IP, 30 req/min default |

---

## How LAN / System Control Works

```
                     ┌──────────────────────────────┐
                     │    authorize_system(request)  │
                     └─────────────┬────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │  ADMIN_TOKEN configured?     │
                    └──────┬─────────────┬────────┘
                           │ Yes         │ No
                           ▼             ▼
              ┌──────────────────┐   ┌──────────────────┐
              │ Token matches?   │   │ Localhost?        │
              └──┬───────────┬───┘   └──┬───────────┬───┘
                 │ Yes       │ No       │ Yes       │ No
                 ▼           ▼          ▼           ▼
              ✅ ALLOW    ❌ 403     ✅ ALLOW   ┌──────────────┐
                                               │ LAN enabled?  │
                                               └──┬────────┬──┘
                                                  │ Yes    │ No
                                                  ▼        ▼
                                           ┌──────────┐ ❌ 403
                                           │ LAN IP?  │
                                           └──┬───┬───┘
                                              │Yes│No
                                              ▼   ▼
                                           ✅  ❌ 403
```

**Defaults:**
- `TRINAXAI_ADMIN_TOKEN` — empty (not set). Localhost access works automatically.
- `TRINAXAI_ALLOW_LAN_SYSTEM` — `0` (disabled). Phones/tablets on WiFi can use the PWA but cannot call system endpoints.
- Enable LAN system control with `--lan-system` during install, which generates a strong random token.

**Testing the security model:**
```bash
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
```

---

## Project Principles

These principles guide all design and contribution decisions:

1. **Local-first** — Everything runs on the user's device. No cloud dependencies, no telemetry, no data exfiltration.
2. **Privacy by default** — Chat data, indexed code, and documents never leave the machine. No accounts, no analytics.
3. **No mandatory cloud** — Ollama runs locally. Optional: users can point to a remote Ollama instance on their own infrastructure.
4. **Confirmations for dangerous actions** — Factory reset, collection deletion, and system shutdown require explicit confirmation headers or interactive prompts.
5. **Security by default** — LAN system control is disabled. Admin tokens are auto-generated when enabled. CORS is restricted to localhost + trusted LAN.
6. **Backward compatibility** — Breaking changes require a migration path. The `rag_api.py` → `app/` migration is incremental.
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
- [Roadmap](../ROADMAP.md) — Planned features and milestones
- [Public Release Checklist](PUBLIC_RELEASE.md) — Pre-release audit steps
