# TrinaxAI Documentation

[Español](README.es.md)

This directory is the entry point for the technical and operational documentation of **TrinaxAI 1.2.0**, released under **AGPL-3.0-or-later**. It documents the current branch. For critical settings and endpoints, also verify `.env.example`, `chat-pwa/package.json`, and FastAPI's generated OpenAPI specification.

For the product overview, screenshots and benchmarks, see the official website: **[trinaxai.app](https://www.trinaxai.app/)**.

## Current capabilities

| Area | Includes | Reference |
|---|---|---|
| Local chat and AI | Ollama, streaming, multi-model routing, and task-aware generation | [Architecture](ARCHITECTURE.md) |
| RAG | 16 AST-aware code parsers, text fallback, vector + BM25, reranking, citations, collections, and source browsing | [Configuration](CONFIGURATION.md) |
| Internet | Optional DuckDuckGo/Brave/SearXNG search, safe page reads, and deep research | [API](API_REFERENCE.md) |
| Agent | CLI and PWA, file/shell tools, workspaces, sandboxing, and approvals | [CLI](CLI_REFERENCE.md) |
| Multimodal | Vision, attachments, document extraction, STT, and TTS | [PWA](../chat-pwa/README.md) |
| Local data | Memory, history, synchronization, statistics, watcher, and backups | [Architecture](ARCHITECTURE.md) |
| Devices | Installable PWA, offline shell, LAN, scoped pairing, and revocation | [Security](SECURITY.md) |
| Operations | Installers, updater, service manager, doctor, and hardware profiles | [README](../README.md) |

## Start here

For a normal installation, download [TrinaxAI Manager for v1.2.0](https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0), open it, and select **Install**. The same application provides **Update** and **Uninstall**. Git and terminal commands are not required.

| Need | Document |
|---|---|
| Install, update, or uninstall with the graphical Manager | [Main README](../README.md#quick-start) |
| Understand components and data flows | [Architecture](ARCHITECTURE.md) |
| Configure models, networking, RAG, and the PWA | [Configuration reference](CONFIGURATION.md) |
| Look up any environment variable | [Environment variable inventory](ENVIRONMENT_VARIABLES.md) |
| Compare local model profiles and measurements | [Model benchmark](MODEL_BENCHMARK.md) |
| Use the terminal interface | [CLI reference](CLI_REFERENCE.md) |
| Integrate an HTTP client | [API reference](API_REFERENCE.md) |
| Develop and debug | [Developer guide](DEVELOPER_GUIDE.md) |
| Fix an error or recover a service | [Troubleshooting and recovery](TROUBLESHOOTING.md) |
| Work on the web interface | [PWA documentation](../chat-pwa/README.md) |
| Validate installers and release checks | [Testing guide](../TESTING.md) |
| Pair a phone and trust local HTTPS | [LAN pairing guide](NETWORK_PAIRING.md) |
| Sign desktop release assets | [Release signing](RELEASE_SIGNING.md) |
| Read the in-app user guide | Open **Settings → Documentation** in the PWA, or see [PWA documentation](../chat-pwa/README.md) |

## Platform installation

- [Linux](INSTALL_LINUX.md)
- [macOS](INSTALL_MACOS.md)
- [Windows](INSTALL_WINDOWS.md)
- [LAN pairing and HTTPS trust](NETWORK_PAIRING.md)
- [Release signing](RELEASE_SIGNING.md)

## Operations and maintenance

- Start from [`.env.example`](../.env.example); never commit `.env`.
- Use `trinaxai doctor` for diagnostics and `trinaxai status` for service state.
- Run `./backup.sh` before upgrades or index changes.
- When an error includes a recovery action, follow it first; otherwise use the
  [troubleshooting decision table](TROUBLESHOOTING.md) before deleting data.
- See [support](SUPPORT.md) for help and [security](SECURITY.md) for vulnerability reports.

## Complete reference map

### Technical references

- [Architecture](ARCHITECTURE.md) — components, data flows, storage, authorization boundaries, and test entry points.
- [API reference](API_REFERENCE.md) — live HTTP contracts, authorization, SSE, uploads, pairing, and errors.
- [Configuration](CONFIGURATION.md) — operational settings, model routing, limits, networking, and recovery behavior.
- [Environment variables](ENVIRONMENT_VARIABLES.md) — canonical `TRINAXAI_*` and `VITE_TRINAXAI_*` inventory.
- [CLI reference](CLI_REFERENCE.md) — commands, slash commands, pairing, TOML, and exit codes.
- [Troubleshooting and recovery](TROUBLESHOOTING.md) — symptom, safe diagnostic, next action, and escalation bundle.
- [Developer guide](DEVELOPER_GUIDE.md) — local setup, conventions, debugging, PWA work, and release checks.
- [Model benchmark](MODEL_BENCHMARK.md) — the checked-in local measurements and their limitations.

### Operations and community

- [Linux installation](INSTALL_LINUX.md), [macOS installation](INSTALL_MACOS.md), and [Windows installation](INSTALL_WINDOWS.md).
- [Testing guide](../TESTING.md) — installer dry-runs and cross-platform release validation.
- [Security policy](SECURITY.md) — reporting channel, threat model, and deployment rules.
- [Support](SUPPORT.md) — the minimum diagnostic bundle for a useful issue.
- [Contributing](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).
- [Trademark](TRADEMARK.md) — permitted use of the TrinaxAI name and logo.
- [Changelog](CHANGELOG.md) — release history and unreleased work.

## Project and contributing

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Sources of truth

| Subject | Authoritative source |
|---|---|
| Python dependencies and tasks | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| CLI commands and flags | `trinaxai_cli/app.py` |
| HTTP endpoints | `app/routes/`, `app/main.py`, `/openapi.json` |
| Environment variables | `docs/ENVIRONMENT_VARIABLES.md`, `.env.example` |
| Frontend scripts | `chat-pwa/package.json` |
| PWA manifest, caching, and proxies | `chat-pwa/vite.config.ts` |
| In-app Docs navigation and links | `chat-pwa/src/components/Docs.tsx`; user-facing copy lives in the linked `docs/*.md` files |
| User-facing error actions | `chat-pwa/src/lib/api_errors.ts`, `chat-pwa/src/components/chat/MessageList.tsx` |

## Documentation conventions

- Files without a suffix are English; `.es.md` files are Spanish.
- Commands run from the repository root unless `cd chat-pwa` is shown.
- Default ports are `3334` (PWA), `3333` (RAG API), and `11434` (Ollama).
- Managed installations prefer HTTPS for the PWA and RAG API; direct HTTP is a
  loopback development fallback. A LAN browser must trust the public CA shown by
  `trinaxai network`.
- Local data paths (`storage/`, `local_sources/`, `logs/`, `backups/`) must not be committed.
- When a user-facing behavior changes, update the canonical English reference and its reviewed `.es.md` translation when applicable, then keep the in-app Docs links current.
- Do not copy secrets, private paths, or generated storage files into examples. Prefer placeholders such as `HOST-LAN-IP` and point to `.env.example` for defaults.
