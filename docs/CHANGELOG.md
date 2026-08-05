# Changelog

All notable changes to TrinaxAI are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

## [1.1.0] — 2026-08-05

### Added

- Added `trinaxai network refresh` and an accessible PWA recovery notice for
  stale cached origins after Wi-Fi, router, or LAN address changes.
- The offline copy can explicitly erase its cache, local data, and service
  worker to remove an installation saved at an old address.
- A new address detects existing server state and opens pairing recovery
  instead of repeating first-time setup.
- The CLI is now translatable through `trinaxai_cli/i18n.py`, covering the
  app, client, doctor, help and interface output.
- The web app ships a manifest per locale, so an installed app keeps its
  language in the launcher.
- Added Spanish guides for the environment-variable inventory and the model
  benchmark.

### Changed

- Community documentation (changelog, contributing, security, support, code of
  conduct, trademark) moved into `docs/`, leaving the root to entry points,
  build and runtime configuration, and lifecycle scripts.
- Translated documents use a single `*.es.md` convention; `docs/es/` is gone.
- `service_manager` returns accurate exit codes on start actions and gained a
  `reload-network` action.
- Static translation data is bundled as its own JavaScript chunk, cutting the
  largest chunk from 384.5 KiB to 302.3 KiB with no change to total size.

### Removed

- Dropped `install_ollama_16gb_profile.sh`, a wrapper that only forwarded to
  `install.sh --profile 16gb`. Use that command directly.

### Fixed

- `trinaxai doctor` caps its service probe at 10s, so a slow service manager is
  reported as a failed check instead of hanging the command.
- Voice calls and web-search settings behave correctly, and i18n coverage now
  extends across chat, the knowledge browser, settings and pairing.
- The installer, update, uninstall and backup scripts are more robust on Linux,
  macOS and Windows.
- Identity and creator answers are resolved deterministically, so small local
  models no longer distort them.
- Spanish pages link Spanish targets; every relative link in the repository
  resolves.

### Security

- Cryptographic material, certificates, credentials and environment files are
  excluded from indexing (`.key`, `.pem`, `.p12`, `.pfx`, `.netrc`,
  `credentials.json`, `secrets.json` and similar).
- Updated `aiohttp` to 3.14.3, clearing CVE-2026-59881, CVE-2026-69243 and
  CVE-2026-69244.
- Patched three high-severity frontend advisories: `brace-expansion` 5.0.9,
  `fast-uri` 3.1.5 and `undici` 7.29.0.

## [1.0.2] — 2026-08-01

### Fixed

- Initialized the Buildx container driver so the GHCR image can be published
  with SBOM and provenance attestations.

## [1.0.1] — 2026-07-31

### Added

- Published release assets through one verified release workflow.
- Added production gateway coverage and cross-platform CLI, installer, service,
  cancellation, timeout and failure-path tests.

### Changed

- Hardware profiles now scale official Qwen3 embeddings from 0.6B/1024d on
  8/16 GB systems to 4B/2560d on `max` and 8B/4096d on `ultra`.
- Docker Compose can start with safe defaults when no `.env` file exists.

### Fixed

- Hardened inference timeouts, TLS verification, proxy identity, API errors,
  cleanup paths and Windows/macOS/Linux release checks.

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

[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.1.0
[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
