# Changelog

All notable changes to TrinaxAI are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/) format.

## [1.0.0] — 2026-07-21

### Added

- Local-first PWA with Ollama chat, cited RAG, optional web research, vision,
  voice and capability-scoped device pairing.
- Hybrid project/document indexing with collections, AST-aware code chunks,
  durable progress, cancellation, retry and safe incremental publication.
- One packaged `trinaxai` CLI for chat, agent, indexing, research, memory,
  collections, watchers, pairing, diagnostics and service lifecycle.
- Tool-using agent constrained to approved workspaces, with confirmation for
  dangerous actions and a network-isolated Linux shell sandbox.
- Cross-platform installers and service supervision for Linux, macOS and
  Windows, plus bilingual product and technical documentation.
- Official RAG API container published to GitHub Container Registry with the
  versioned `1.0.0` tag and rolling `1.0`, `1` and `latest` tags.

### Changed

- Automatic model profiles cover low-memory through 64+ GB systems and use
  multilingual `qwen3-embedding:0.6b` embeddings by default.
- The PWA includes refreshed install icons, a clearer Call Mode and accessible
  reduced-motion behavior.
- CLI HTTPS remains verified and accepts private certificate authorities through
  `--ca-file` or `TRINAXAI_CA_FILE`.

### Fixed

- Plain greetings in automatic CLI mode use normal Ollama chat instead of
  forcing an empty RAG lookup.
- Generation, RAG, research, agent, memory, pairing, service and web-search
  failures now terminate predictably and preserve shared state.
- Microphone streams, Web Audio nodes, timers, previews and upload listeners are
  released on cancellation, navigation and errors.
- Large documents and uploads use bounded batches, timeouts and cleanup paths;
  failed indexing never publishes a partial generation.
- Packaging now exposes only the modular CLI and produces a consistent wheel,
  source archive, installers and checksums.

### Security

- Ollama base URLs are centrally restricted to valid HTTP(S) endpoints before
  network access by the backend, CLI, agent and diagnostics.
- Trusted-proxy assertions are signed, short-lived and single-use; protected
  operations require scoped pairing or explicit administration credentials.
- CI checks Python and frontend dependencies, static high-severity findings,
  committed secrets, package builds, browser flows and public-release readiness.

[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
