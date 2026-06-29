# Roadmap

This roadmap keeps V1 focused on reliability before adding breadth. Timelines are approximate and community-driven.

---

## ✅ V1 (Completed — June 2026)

- [x] Stable local chat through Ollama
- [x] RAG over imported folders and indexed projects
- [x] PWA access from desktop and trusted LAN phones
- [x] Explicit local memory with auto-summarization
- [x] Cross-platform install paths for Linux, macOS, and Windows
- [x] Public release checks, security notes, support docs, and contribution flow
- [x] Hybrid retrieval with optional reranker
- [x] File watcher for auto-reindexing
- [x] Cross-device state sync
- [x] Deep research mode (multi-pass)

---

## 🔜 Near-Term (Q3 2026)

- [ ] **Visual project browser** — Tree view of indexed files in the PWA
- [ ] **Conversation summarization** — Auto-summarize long chats to save context window
- [ ] **Structured indexer events** — More granular progress from index.py for better ETA
- [ ] **Richer collection/project browser** — Inspect and search indexed sources visually
- [ ] **Prompt templates** — Save and reuse custom system prompts per collection
- [ ] **API rate limit tuning** — Configurable per-user limits

---

## 📅 Mid-Term (Q4 2026+)

- [ ] **Docker/Compose deployment** — Reproducible containerized stack (for advanced users)
- [ ] **More model profiles** — Auto-detection for GPU-heavy machines (RTX 4090, M2 Ultra)
- [ ] **Plugin system** — Tool extensions via Python entry points
- [ ] **E2E test coverage** — PWA smoke tests (Playwright) and installer tests
- [ ] **MCP server** — Model Context Protocol for IDE integration beyond Continue.dev
- [ ] **Obsidian integration** — Two-way sync with Obsidian vaults

---

## 🚀 Later

- [ ] **Mobile push notifications** — Service worker background sync for long-running tasks
- [ ] **Multi-user support** — Per-user collections, memory, and chat history
- [ ] **OpenAPI/Swagger docs** — Auto-generated from FastAPI app
- [ ] **WebSocket streaming** — Bidirectional chat for lower latency
- [ ] **CLI TUI** — Terminal-based UI with rich widgets (beyond REPL)
- [ ] **Benchmark suite** — Performance regression tests for retrieval and indexing

---

## Contributing

Want to work on something? Check the [issues](https://github.com/TrinaxCode/TrinaxAI/issues) or open a discussion. PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
