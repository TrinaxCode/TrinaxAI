# Changelog

All notable changes to TrinaxAI are documented here. This project follows [Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

## [1.2.0] — 2026-07-18

### Added
- System-protected, write-only web-search settings and connection tests for DuckDuckGo, Brave Search, and SearXNG.

### Changed
- Automatic model profiles now cover 1–8 GB, 9–31 GB, 32–63 GB, and 64+ GB RAM while preserving environment overrides and multilingual `bge-m3` embeddings.
- Playwright uses an isolated TrinaxAI preview server on a dedicated configurable port.

### Fixed
- Generation, RAG, research, agent, memory, pairing, services, web search, and CLI error paths now fail predictably and preserve shared state under concurrent updates.
- Installers no longer remove Ollama models that may belong to other projects.

### Security
- Agent validates Ollama endpoints before network access; release gates audit dependencies, high-severity static findings, and secrets.

## [1.1.0] — 2026-07-16

### Added
- Persistent global sound-effects preference and centralized cues for generation, tools, files, Agent Mode, voice, Call Mode, cancellation, errors, and confirmations.
- Durable file-index jobs with real phase/page/chunk/batch progress, cancellation, retry, deduplication, stage/total timeouts, and reconnectable status polling.
- Regression coverage for microphone lifecycle, SSE termination, indexing failures and recovery, duplicate uploads, temporary-file cleanup, and 160-page text PDFs.

### Fixed
- Speech-to-Text and Call Mode now share one microphone lifecycle; exiting, cancelling, navigating, or unmounting stops tracks, recorders, Web Audio nodes, recognition restarts, TTS, and pending transcription.
- First-token waits and attachment indexing now have bounded, recoverable timeouts instead of infinite loading or waiting audio.
- Large PDFs are processed and embedded in bounded page/chunk batches instead of retaining the full pipeline in memory.
- CI clean installs no longer combine hash-locked runtime requirements with unhashed developer requirements in one pip invocation.
- Global synchronization/device monitors, toast exit timers, previews, and upload abort listeners now release their resources.

### Changed
- Failed or cancelled indexing attempts preserve a safe retry path and never publish partial index generations.
- Search Mode and RAG surface explicit recoverable errors when providers, streams, indexes, or models are unavailable.

### Added
- Local-first PWA with Ollama chat, RAG, voice, image analysis, and phone/LAN access
- Project and folder indexing with collections, progress tracking, cancellation, and citations
- AST-aware chunking for 15+ programming languages via tree-sitter
- Hybrid retrieval (vector + BM25 + optional reranker)
- Multi-model auto-routing heuristic (no LLM overhead)
- Cross-platform service manager (systemd, launchctl, subprocess)
- Developer CLI (`trinaxai ask`, `trinaxai chat`, `trinaxai index`, `trinaxai doctor`, etc.)
- Modular CLI package (`trinaxai_cli/`) with subcommands: browse, collections, doctor, export, index, memory, obsidian, research, watch
- Conversation memory (explicit "remember that" facts persisted locally)
- Deep research mode with multi-pass RAG decomposition
- Optional web search through DuckDuckGo, Brave Search, or SearXNG with bounded public-page reads
- Shared CLI/PWA agent with authorized workspaces, session-bound approval, and cooperative cancellation
- Capability-scoped LAN pairing; local chat remains available without exposing private data
- File system watcher for auto-reindexing on changes
- Cross-device shared state sync via local backend
- Usage statistics aggregation from JSONL logs
- Spanish/English bilingual UI with parity-checked i18n keys
- Host-backed chat attachments with IndexedDB fallback for offline or older-backend sessions
- Bilingual documentation hub and dedicated API, CLI, configuration, architecture, installation, PWA, and developer references
- Dark/light theme with system preference detection
- Full PWA installability (iOS, Android, desktop)
- Self-signed HTTPS for local LAN access
- Continue.dev VSCode integration config
- One-command installers for Linux (install.sh), macOS (install.sh), and Windows (install.ps1)
- Pre-release audit tool (scripts/public_readiness.py)
- System health test (test_system.py)
- PWA update notification component (PwaUpdater)
- Offline fallback page
- FAQ section in README

### Changed
- Stronger product identity: assistant identifies as TrinaxAI, not as the project author
- Licensed under AGPL-3.0-or-later
- PWA manifest: fixed display mismatch, added categories, dir, lang, shortcuts, display_override
- PWA icons: removed duplicate Apple touch icon sizes, improved splash screen handling
- README rewritten with CLI section, security model, FAQ, and improved structure
- SECURITY.md expanded with threat model and deployment recommendations

### Fixed
- Chat history compaction prevents localStorage quota errors
- Image preprocessing prevents vision model OOM errors
- Voice mode handles sentence-level TTS with interrupt support
- KnowledgeBrowser page was unreachable from App router
- iOS splash screen used wrong icon size on all devices
- PWA manifest had display mode mismatch (standalone vs fullscreen)
- Missing includeAssets in service worker precache (new logo variants)
- backup.sh now validates tarball contents before extraction (path traversal protection)
- uninstall.sh no longer removes systemd units before user confirmation
- Ollama installer binds to 127.0.0.1 by default (not 0.0.0.0)

### Security
- LAN system control disabled by default (was enabled); explicit opt-in via --lan-system
- PUT /app-state endpoint now requires system authorization
- collection_id sanitized with _collection_slug before passing to subprocess
- Admin token auto-generated when enabling LAN system control
- bare except Exception replaced with specific exception types across Python files
- create_ssl_context consolidated to single implementation in config.py
- Removed unused requests dependency from requirements.txt
- Dead code removed: importAndIndexFolder from api.ts, unused import ssl from config.py

## [1.0.0] — 2026-06-28

### Added
- Initial public TrinaxAI release.

[1.2.0]: https://github.com/TrinaxCode/TrinaxAI/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
