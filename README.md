<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a>
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="README.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="docs/README.md">Documentation</a> · <a href="docs/CHANGELOG.md">Changelog</a> · <a href="LICENSE">License</a></sub></p>

> Your private assistant for working with your files on your own computer.

TrinaxAI is a local-first assistant built around Ollama. It combines direct
chat, cited RAG, optional web research, a sandboxed coding agent, a CLI, and an
installable PWA. Inference and indexed data stay on the configured host unless
you explicitly choose a remote service.

## Quick start

### Linux and macOS

The stable release installer detects CPU, RAM, GPU, and VRAM, selects a safe
model profile, verifies the source archive checksum, builds the PWA, checks
Ollama and the required models, runs a smoke inference, and starts the app.

```bash
set -e; version="1.2.1"; base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"; installer="$(mktemp)"; trap 'rm -f "$installer"' EXIT; curl -fsSL "$base/TrinaxAI-${version}-installer.sh" -o "$installer"; expected="$(curl -fsSL "$base/SHA256SUMS" | awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }')"; actual="$( (shasum -a 256 "$installer" 2>/dev/null || sha256sum "$installer") | awk '{print $1}' )"; test "$expected" = "$actual"; bash "$installer"
```

### Windows PowerShell

```powershell
$ErrorActionPreference="Stop"; $version="1.2.1"; $base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"; $installer=Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"; Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer; $line=Invoke-RestMethod -Uri "$base/SHA256SUMS" | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1; $expected=if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash; if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }; & $installer
```

The release installers are intentionally pinned and never fall back to
`main`. For an independently verified download, use the short commands in
[Release signing](docs/RELEASE_SIGNING.md) before execution. A local checkout
(`bash install.sh` or `powershell -ExecutionPolicy Bypass -File .\install.ps1`)
is the operator/development path.

When installation finishes, open **https://localhost:3334**. If you use
`--no-models`, every configured Ollama model must already be installed; the
installer still verifies each model before it reports success.

Useful options:

```bash
bash install.sh --no-start       # prepare without starting services
bash install.sh --profile 16gb  # override the detected profile
```

```powershell
.\install.ps1 -NoStart
.\install.ps1 -Profile 16gb
```

Update or remove an existing installation with the guided scripts:

```bash
bash update.sh
bash uninstall.sh
```

```powershell
.\update.ps1
.\uninstall.ps1
```

See the platform guides for prerequisites, certificates, LAN pairing, Docker,
and recovery: [Linux](docs/INSTALL_LINUX.md), [macOS](docs/INSTALL_MACOS.md),
and [Windows](docs/INSTALL_WINDOWS.md).

## What you get

- Direct Ollama chat and deterministic routing for chat, code, reasoning, and math.
- Hybrid RAG over code and documents with citations, collections, incremental indexing, and an optional reranker.
- A sandboxed coding agent limited to approved workspace roots.
- Optional web search, deep research, memory, voice, and vision.
- An HTTPS PWA for desktop and mobile, with revocable device pairing and local-first synchronization.
- A CLI for chat, indexing, research, lifecycle, diagnostics, and exports.

## Models and hardware

The installer uses CPU, RAM, GPU, and VRAM to choose one of four profiles. Apple
Silicon uses unified memory. You can override the profile in `.env` or with
`--profile` / `-Profile`.

| Profile | Chat/code | Fast | Embeddings |
| --- | --- | --- | --- |
| `8gb` | `qwen3.5:2b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `16gb` | `qwen3.5:4b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `32gb` | `qwen3.5:9b` | `qwen3.5:4b` | `qwen3-embedding:4b` |
| `64gb` | `qwen3.5:35b` / `qwen3-coder:30b` | `qwen3.5:4b` | `qwen3-embedding:4b` |

The `8gb` profile is CPU-friendly; no GPU is required. Large models are pulled
only when the selected profile needs them. See [configuration](docs/CONFIGURATION.md)
to change model names or resource limits.

## CLI

After installation, the `trinaxai` command is available in a new terminal:

```bash
trinaxai ask "Summarize my indexed project" --engine rag
trinaxai index .
trinaxai agent --workspace .
trinaxai research --query "Compare these documents" --depth 2
trinaxai doctor --strict --json
trinaxai start
trinaxai stop
trinaxai status
```

Run `trinaxai --help` or read the [CLI reference](docs/CLI_REFERENCE.md) for
all commands. `trinaxai doctor` is the fastest first diagnostic.

## Privacy and security

Services bind to loopback by default. Ollama is never exposed as a generic
proxy. LAN browsers must pair with a one-time code and receive only explicit
capabilities; indexing, administration, agent tools, and model management stay
host-only. The agent is sandboxed and dangerous actions require approval.

Keep ports `3333` and `11434` private, keep `storage/.proxy_secret` protected,
and use a VPN instead of opening the host to the public Internet. Read the
[security guide](docs/SECURITY.md), [pairing guide](docs/NETWORK_PAIRING.md),
and [release-signing guide](docs/RELEASE_SIGNING.md).

## Supported platforms

| Platform | Installer | Service lifecycle | Automated coverage |
| --- | --- | --- | --- |
| Linux (Ubuntu, Debian, Fedora, Arch) | `install.sh` | user systemd | backend, CLI, PWA, E2E, installer |
| macOS (Intel and Apple Silicon) | `install.sh` | launchctl | backend, CLI, shell installer |
| Windows 10/11 | `install.ps1` | subprocess supervisor | backend, CLI, PowerShell installer |

The release is tested on pinned GitHub-hosted runners. Real model downloads,
permissions, and first-run certificates depend on the target machine; use
[TESTING.md](TESTING.md) for the clean-machine smoke checklist.

## Documentation

Start at the [documentation hub](docs/README.md). The most-used references are:

- [Architecture and data flow](docs/ARCHITECTURE.md)
- [Configuration](docs/CONFIGURATION.md)
- [Environment variables](docs/ENVIRONMENT_VARIABLES.md)
- [HTTP API](docs/API_REFERENCE.md)
- [Troubleshooting and recovery](docs/TROUBLESHOOTING.md)
- [Continue.dev setup](continue-config.yaml)
- [Development guide](docs/DEVELOPER_GUIDE.md)

The PWA also includes the same documentation under **Docs**.

## Development

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock
(cd chat-pwa && npm ci && npm run dev)
```

Run `make check` before sending a change. It covers lint, formatting, typing,
tests, deterministic RAG, frontend checks, the PWA build, and bundle budgets.
See [CONTRIBUTING](docs/CONTRIBUTING.md) for the full workflow.

## License

TrinaxAI is AGPL-3.0-or-later. See [LICENSE](LICENSE) and the
[trademark guide](docs/TRADEMARK.md).

Built by [TrinaxCode](https://github.com/TrinaxCode) · [trinaxai.app](https://www.trinaxai.app/)
