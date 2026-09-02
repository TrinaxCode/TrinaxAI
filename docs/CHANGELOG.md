<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🧭 Changelog
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="CHANGELOG.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

All notable changes to TrinaxAI are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

### Changed

- Split the frontend API into domain modules behind a stable `api.ts` facade.
- Split Agent rendering, execution, voice and shared contracts into focused
  modules while preserving the existing public behavior and tests.
- Kept RAG generation, streaming, runtime, indexing and chat responsibilities
  behind small compatibility facades instead of growing release entry points.

### Documentation

- Added a bilingual troubleshooting and recovery guide that maps common errors
  to safe next actions, including the PWA's **Open indexing** flow for empty
  collections.
- Aligned README, API, CLI, configuration, PWA, support, and in-app Docs with
  current profiles, HTTPS trust, recoverable jobs, and the reserved MCP command.

## [1.2.1] — 2026-09-02

### Changed

- Promoted the validated desktop release to Production/Stable and aligned the
  Python package, CLI, PWA, installers, updater, and documentation on one version.
- Simplified the public installation path to one short command per platform while
  keeping release archives checksum-verified and signed.
- Pinned the release public key in the repository and closed the remaining
  dependency alerts.

### Fixed

- Standalone RAG evaluation now imports the repository package from a clean
  checkout, matching the isolated CLI wheel contract.
- PowerShell release URLs parse correctly on Windows and the installer refuses
  unverified or unpinned source packages.

## [1.2.0] — 2026-08-17

### Added

- Added a collapsible thinking trace with elapsed time, explicit completion
  metadata, and bounded automatic continuation for length-limited answers.
- Added autonomous chat-mode routing across web search, deep research, local
  knowledge and Agent tools, while preserving explicit user overrides.
- Added retained chat attachments with mobile PDF fallbacks, Office downloads,
  and localhost-only native application opening.
- Added a loopback recovery page for a stopped installation, a desktop service
  manager, hardware-aware model profiles, and lifecycle installer dry-runs.

### Changed

- Host administration is now fail-closed and localhost-only. Paired LAN devices
  are limited to chat, private-read and web scopes, and the PWA renders controls
  from the effective capability reported by the server.
- The Windows installer now writes the same canonical `8gb`, `16gb`, `32gb`, and
  `64gb` profiles as the backend, while migrating legacy `max`/`ultra` values.
- `trinaxai network` now prints the public CA/certificate path needed to trust a
  LAN browser, with a bilingual Android/iOS pairing and HTTPS guide.
- English and Spanish setup, security, API, CLI and testing guides now describe
  the current installers, recovery flow, model selection and LAN boundaries.
- Expanded the documentation hub and configuration/API references, aligned the
  in-app PWA Docs with the repository, and replaced its placeholder architecture
  image with an accessible overview.

### Fixed

- Long chat, RAG, research and Agent responses now terminate with an explicit
  complete, length, cancelled or error state instead of silently appearing
  complete after truncation.
- Improved responsive PWA navigation, keyboard/focus behavior, accessible
  labels, offline handling and attachment actions across desktop, tablet and
  phone viewports.
- Release publication now builds signed source archives, installers, and the
  CLI-only wheel, includes them in `SHA256SUMS`, and verifies every published
  asset after download.

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
  memory-constrained systems to 4B/2560d on 32/64 GB systems.
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

- Automatic model profiles cover memory-constrained through 64+ GB systems and use
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

[1.2.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1
[1.2.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0
[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.1.0
[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
