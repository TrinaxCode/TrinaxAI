# TrinaxAI Documentation

This directory is the entry point for the technical and operational documentation of **TrinaxAI 1.2.0**, released under **AGPL-3.0-or-later**. It documents the current branch. For critical settings and endpoints, also verify `.env.example` and FastAPI's generated OpenAPI specification.

## 1.2.0 capabilities

| Area | Includes | Reference |
|---|---|---|
| Local chat and AI | Ollama, streaming, multi-model routing, and task-aware generation | [Architecture](ARCHITECTURE.md) |
| RAG | AST indexing, vector + BM25, reranking, citations, collections, and source browsing | [Configuration](CONFIGURATION.md) |
| Internet | Optional DuckDuckGo/Brave/SearXNG search, safe page reads, and deep research | [API](API_REFERENCE.md) |
| Agent | CLI and PWA, file/shell tools, workspaces, sandboxing, and approvals | [CLI](CLI_REFERENCE.md) |
| Multimodal | Vision, attachments, document extraction, STT, and TTS | [PWA](../chat-pwa/README.md) |
| Local data | Memory, history, synchronization, statistics, watcher, and backups | [Architecture](ARCHITECTURE.md) |
| Devices | Installable PWA, offline shell, LAN, scoped pairing, and revocation | [Security](../SECURITY.md) |
| Operations | Installers, updater, service manager, doctor, and hardware profiles | [README](../README.md) |

## Start here

| Need | Document |
|---|---|
| Install and use TrinaxAI | [Main README](../README.md) |
| Understand components and data flows | [Architecture](ARCHITECTURE.md) |
| Configure models, networking, RAG, and the PWA | [Configuration reference](CONFIGURATION.md) |
| Look up any environment variable | [Environment variable inventory](ENVIRONMENT_VARIABLES.md) |
| Use the terminal interface | [CLI reference](CLI_REFERENCE.md) |
| Integrate an HTTP client | [API reference](API_REFERENCE.md) |
| Develop and debug | [Developer guide](DEVELOPER_GUIDE.md) |
| Work on the web interface | [PWA documentation](../chat-pwa/README.md) |

## Platform installation

- [Linux](INSTALL_LINUX.md)
- [macOS](INSTALL_MACOS.md)
- [Windows](INSTALL_WINDOWS.md)

## Operations and maintenance

- Start from [`.env.example`](../.env.example); never commit `.env`.
- Use `trinaxai doctor` for diagnostics and `trinaxai status` for service state.
- Run `./backup.sh` before upgrades or index changes.
- See [support](../SUPPORT.md) for help and [security](../SECURITY.md) for vulnerability reports.

## Project and contributing

- [Contributing](../CONTRIBUTING.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Changelog](../CHANGELOG.md)

## Sources of truth

| Subject | Authoritative source |
|---|---|
| Python dependencies and tasks | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| CLI commands and flags | `trinaxai_cli/app.py` |
| HTTP endpoints | `app/routes/`, `app/main.py`, `/openapi.json` |
| Environment variables | `docs/ENVIRONMENT_VARIABLES.md`, `.env.example` |
| Frontend scripts | `chat-pwa/package.json` |
| PWA manifest, caching, and proxies | `chat-pwa/vite.config.ts` |

## Documentation conventions

- Files without a suffix are English; `.es.md` files are Spanish.
- Commands run from the repository root unless `cd chat-pwa` is shown.
- Default ports are `3334` (PWA), `3333` (RAG API), and `11434` (Ollama).
- Local data paths (`storage/`, `local_sources/`, `logs/`, `backups/`) must not be committed.
