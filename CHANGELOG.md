# Changelog

All notable changes to TrinaxAI are documented here. This project follows [Keep a Changelog](https://keepachangelog.com/) format.

## [1.0.0] — 2026-06-27

### Added
- Local-first PWA with Ollama chat, RAG, voice, image analysis, and phone/LAN access
- Project and folder indexing with collections, progress tracking, cancellation, and citations
- AST-aware chunking for 15+ programming languages via tree-sitter
- Hybrid retrieval (vector + BM25 + optional reranker)
- Multi-model auto-routing heuristic (no LLM overhead)
- Cross-platform service manager (systemd, launchctl, subprocess)
- Conversation memory (explicit "remember that" facts persisted locally)
- Deep research mode with multi-pass RAG decomposition
- File system watcher for auto-reindexing on changes
- Cross-device shared state sync via local backend
- Usage statistics aggregation from JSONL logs
- Spanish/English bilingual UI with i18n system
- Dark/light theme with system preference detection
- Full PWA installability (iOS, Android, desktop)
- Self-signed HTTPS for local LAN access
- Continue.dev VSCode integration config
- One-command installers for Linux (install.sh), macOS (install.sh), and Windows (install.ps1)
- Pre-release audit tool (scripts/public_readiness.py)
- System health test (test_system.py)
- CI pipeline with DCO check, Python compile, TypeScript type check, and build

### Changed
- Stronger product identity: assistant identifies as TrinaxAI, not as the project author
- Licensed under AGPL-3.0-or-later
- query.py marked deprecated in favor of trinaxai_cli/ package

### Fixed
- Chat history compaction prevents localStorage quota errors
- Image preprocessing prevents vision model OOM errors
- Voice mode handles sentence-level TTS with interrupt support

[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
