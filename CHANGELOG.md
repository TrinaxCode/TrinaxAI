# Changelog

All notable changes to TrinaxAI are documented here. This project follows [Keep a Changelog](https://keepachangelog.com/) format.

## [1.0.0] — Unreleased

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
- File system watcher for auto-reindexing on changes
- Cross-device shared state sync via local backend
- Usage statistics aggregation from JSONL logs
- Spanish/English bilingual UI with i18n system (257 keys per language)
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
- query.py marked deprecated in favor of trinaxai_cli/ package
- PWA manifest: fixed display mismatch, added categories, dir, lang, shortcuts, display_override
- PWA icons: removed duplicate Apple touch icon sizes, improved splash screen handling
- README rewritten with CLI section, security model, FAQ, and improved structure
- SECURITY.md expanded with threat model and deployment recommendations
- ROADMAP reorganized into Done / In Progress / Planned / Future Ideas

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

[1.0.0]: https://github.com/TrinaxCode/TrinaxAI
