# TrinaxAI Documentation

This directory is the entry point for TrinaxAI's technical and operational documentation. It documents the current branch. For critical settings and endpoints, also verify `.env.example` and FastAPI's generated OpenAPI specification.

## Start here

| Need | Document |
|---|---|
| Install and use TrinaxAI | [Main README](../README.md) |
| Understand components and data flows | [Architecture](ARCHITECTURE.md) |
| Configure models, networking, RAG, and the PWA | [Configuration reference](CONFIGURATION.md) |
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

## Contributing and releasing

- [Contributing](../CONTRIBUTING.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Release checklist](PUBLIC_RELEASE.md)
- [Changelog](../CHANGELOG.md)
- [Roadmap](../ROADMAP.md)

## Sources of truth

| Subject | Authoritative source |
|---|---|
| Python dependencies and tasks | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| CLI commands and flags | `trinaxai_cli/app.py` |
| HTTP endpoints | `rag_api.py`, `app/routes/voice.py`, `/openapi.json` |
| Environment variables | `.env.example`, `config.py`, `service_manager.py`, `chat-pwa/vite.config.ts` |
| Frontend scripts | `chat-pwa/package.json` |
| PWA manifest, caching, and proxies | `chat-pwa/vite.config.ts` |

## Documentation conventions

- Files without a suffix are English; `.es.md` files are Spanish.
- Commands run from the repository root unless `cd chat-pwa` is shown.
- Default ports are `3334` (PWA), `3333` (RAG API), and `11434` (Ollama).
- Local data paths (`storage/`, `local_sources/`, `logs/`, `backups/`) must not be committed.

