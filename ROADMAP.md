# Roadmap

This roadmap keeps V1 focused on reliability before adding breadth. Timelines are approximate and community-driven.

---

## ✅ V1 (Done)

- [x] Stable local chat through Ollama
- [x] RAG over imported folders and indexed projects
- [x] PWA access from desktop and trusted LAN phones
- [x] Explicit local memory with auto-summarization
- [x] Cross-platform install paths (Linux, macOS, Windows)
- [x] Public release checks, security notes, support docs, and contribution flow
- [x] Hybrid retrieval with optional reranker
- [x] File watcher for auto-reindexing
- [x] Cross-device state sync
- [x] Deep research mode (multi-pass)
- [x] Developer CLI (`trinaxai ask`, `trinaxai chat`, `trinaxai index`, `trinaxai doctor`)
- [x] Secure defaults: LAN system control disabled, admin token auto-generation
- [x] Bilingual README, FAQ, security model docs, and install guides
- [x] Knowledge browser for collections, files, chunks, search, and deletion
- [x] Background indexing jobs with progress, ETA, and cancellation
- [x] Reusable prompt templates in the PWA
- [x] FastAPI-generated OpenAPI, Swagger UI, and ReDoc
- [x] Backend pytest and frontend Vitest suites in CI

---

## 🔜 In Progress / Near-Term

- [ ] **Screenshots and demo GIFs** — Visual proof of the PWA and CLI in action
- [ ] **Knowledge tree view** — Add hierarchical folders on top of the existing knowledge browser
- [ ] **Conversation summarization** — Auto-summarize long chats to save context window
- [ ] **Indexer telemetry** — Improve phase timing and ETA accuracy for very large imports
- [ ] **CI security expansion** — Add CodeQL, Gitleaks, Semgrep, and Trivy

---

## 📅 Planned

- [ ] **Test coverage expansion** — Add interaction/accessibility tests and raise backend branch coverage
- [ ] **Docker/Compose deployment** — Reproducible containerized stack (for advanced users)
- [ ] **More model profiles** — Auto-detection for GPU-heavy machines (RTX 4090, M2 Ultra)
- [ ] **API rate limit tuning** — Configurable per-user limits
- [ ] **MCP server** — Model Context Protocol for IDE integration beyond Continue.dev
- [ ] **Obsidian integration** — Two-way sync with Obsidian vaults

---

## 🚀 Future Ideas

- [ ] **Plugin system** — Tool extensions via Python entry points
- [ ] **Mobile push notifications** — Service worker background sync
- [ ] **Multi-user support** — Per-user collections, memory, and history
- [ ] **WebSocket streaming** — Bidirectional chat for lower latency
- [ ] **Benchmark suite** — Performance regression tests for retrieval and indexing

---

## Contributing

Want to work on something? Check the [issues](https://github.com/TrinaxCode/TrinaxAI/issues) or open a discussion. PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
