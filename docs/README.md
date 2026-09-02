<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 📚 Documentation
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="README.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

This directory is the entry point for the technical and operational documentation of **TrinaxAI 1.2.1**, the current Production/Stable release under **AGPL-3.0-or-later**. It documents the release branch. For critical settings and endpoints, also verify `.env.example`, `chat-pwa/package.json`, and FastAPI's generated OpenAPI specification.

For the product overview, screenshots and benchmarks, see the official website: **[trinaxai.app](https://www.trinaxai.app/)**.

> Release status: `v1.2.1` is the current Production/Stable release. Its source archives, installers, wheel, checksums, and detached signatures are published on GitHub. Installers are pinned and never fall back to `main`.

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

For a normal installation, run the one-line command for your platform. Git is not required:

```bash
set -e; version="1.2.1"; base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"; installer="$(mktemp)"; trap 'rm -f "$installer"' EXIT; curl -fsSL "$base/TrinaxAI-${version}-installer.sh" -o "$installer"; expected="$(curl -fsSL "$base/SHA256SUMS" | awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }')"; actual="$( (shasum -a 256 "$installer" 2>/dev/null || sha256sum "$installer") | awk '{print $1}' )"; test "$expected" = "$actual"; bash "$installer"
```

On Windows PowerShell, use the same review-before-execute flow with a release-pinned installer:

```powershell
$ErrorActionPreference="Stop"; $version="1.2.1"; $base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"; $installer=Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"; Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer; $line=Invoke-RestMethod -Uri "$base/SHA256SUMS" | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1; $expected=if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash; if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }; & $installer
```

The installer validates the signed release source archive and its SHA-256
manifest. For a manual review or independent GPG check, use
[Release signing](RELEASE_SIGNING.md).

| Need | Document |
|---|---|
| Install, update, or uninstall from a terminal | [Main README](../README.md#quick-start) |
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
