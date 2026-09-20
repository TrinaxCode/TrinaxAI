<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 📚 Documentation
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.6"><img src="https://img.shields.io/badge/version-1.2.6-006bbd" alt="Stable release: 1.2.6"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
</p>

<p align="center"><sub><strong>English</strong> · <a href="README.es.md">Español</a></sub></p>
<p align="center"><sub><a href="../README.md">Home</a> · <a href="https://www.trinaxai.app/">Website</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

This hub takes you from a working npm installation to daily use, configuration,
pairing, recovery, and development. It describes TrinaxAI v1.2.6, the current
stable release.

## Install once

The public installation path is the npm launcher. It works on Linux, macOS, and
Windows:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The launcher downloads the matching release installer and verifies its
SHA-256 checksum before setup. You do not need to clone the repository or run
the platform scripts for a normal installation.

After setup, verify the local services:

~~~bash
trinaxai doctor
trinaxai status
~~~

Open [https://localhost:3334](https://localhost:3334) to use the PWA. See the
[main README](../README.md) for the first question and the daily command map.

## Choose a guide

| Your task | Guide |
| --- | --- |
| Understand the first run on your platform | [Linux](INSTALL_LINUX.md), [macOS](INSTALL_MACOS.md), or [Windows](INSTALL_WINDOWS.md) |
| Configure models, RAG, limits, or networking | [Configuration](CONFIGURATION.md) |
| Find an environment variable | [Environment variables](ENVIRONMENT_VARIABLES.md) |
| Use the terminal interface | [CLI reference](CLI_REFERENCE.md) |
| Pair another device | [LAN pairing](NETWORK_PAIRING.md) |
| Fix a failed health check | [Troubleshooting](TROUBLESHOOTING.md) |
| Understand storage and data flow | [Architecture](ARCHITECTURE.md) |
| Integrate the HTTP service | [API reference](API_REFERENCE.md) |
| Develop or contribute | [Developer guide](DEVELOPER_GUIDE.md) |

## Platform guides

The platform pages explain requirements, what the npm setup command does,
first-run checks, service lifecycle, backups, local networking, and
platform-specific recovery. They do not offer a second installation command.

- [Linux](INSTALL_LINUX.md): systemd, distributions, permissions, and Docker notes
- [macOS](INSTALL_MACOS.md): Apple Silicon, launchd, certificates, and local networking
- [Windows](INSTALL_WINDOWS.md): PowerShell, process supervision, firewall, and WSL notes

## Operate safely

Use these commands from any directory:

~~~bash
trinaxai status
trinaxai doctor --strict
trinaxai update
trinaxai uninstall
~~~

Back up before upgrades or index changes. Keep ports 3333, 3334, and 11434
private unless you understand the LAN pairing and certificate flow. The
[security guide](SECURITY.md) explains the trust boundaries.

## Technical references

- [Architecture](ARCHITECTURE.md): components, data flows, storage, and authorization boundaries
- [Configuration](CONFIGURATION.md): models, RAG, networking, limits, and recovery behavior
- [Environment variables](ENVIRONMENT_VARIABLES.md): the canonical TRINAXAI inventory
- [CLI reference](CLI_REFERENCE.md): commands, flags, pairing, and exit codes
- [API reference](API_REFERENCE.md): HTTP contracts, SSE, uploads, pairing, and errors
- [Model benchmark](MODEL_BENCHMARK.md): checked-in local measurements and limitations
- [PWA documentation](../chat-pwa/README.md): frontend flows, caching, and testing

## Recovery and support

Start with trinaxai doctor. Then use the
[troubleshooting decision tables](TROUBLESHOOTING.md). Include the redacted
diagnostic output and the relevant service status when you open an issue.

Read [support](SUPPORT.md) for the issue bundle and [security](SECURITY.md) for
private vulnerability reports.

## Development and releases

The developer path is intentionally separate from user installation. Start with
the [developer guide](DEVELOPER_GUIDE.md), then use the
[contributing guide](CONTRIBUTING.md) and [testing guide](../TESTING.md).

Release operators can use [release signing](RELEASE_SIGNING.md). The npm
launcher is the supported public entrypoint; the signed platform installers
remain release implementation details.

## Language and source conventions

- Files without a suffix are English; .es.md files are Spanish
- User-facing behavior changes update the English reference and its Spanish translation
- Commands run from the repository root unless a guide says to enter chat-pwa
- Default ports are 3334 for the PWA, 3333 for the RAG API, and 11434 for Ollama
- Do not copy secrets, private paths, or generated storage files into examples

Authoritative sources live in pyproject.toml, chat-pwa/package.json,
trinaxai_cli/app.py, app/routes/, .env.example, and the linked reference
documents. The in-app Docs view reads the same Markdown files.
