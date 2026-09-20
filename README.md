<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="220" valign="middle"></a>
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.6"><img src="https://img.shields.io/badge/version-1.2.6-006bbd" alt="Stable release: 1.2.6"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="README.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="docs/README.md">Documentation</a> · <a href="docs/CHANGELOG.md">Changelog</a> · <a href="LICENSE">License</a></sub></p>

> A private, local-first assistant for your files, research, and code.

TrinaxAI runs on your computer and keeps inference and indexed data on the
configured host unless you explicitly choose a remote service. It combines
local chat, cited retrieval-augmented generation (RAG), optional web research,
a sandboxed coding agent, a terminal interface, and an installable progressive
web app (PWA).

## Install with npm

Use the npm package on Linux, macOS, or Windows. You need Node.js 22 or newer
with npm available in your terminal.

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The launcher downloads the matching official release, verifies its SHA-256
checksum, and starts the platform setup. The setup flow prepares the backend,
PWA, Ollama, and recommended models. It asks before optional model downloads
and autostart changes.

The npm launcher is the only supported end-user installation path. The
platform scripts in this repository implement the release behind the launcher;
you do not need to download or run them directly.

## Start using TrinaxAI

Run the health check first:

~~~bash
trinaxai doctor
trinaxai status
~~~

Then open [https://localhost:3334](https://localhost:3334). Your browser may
ask you to trust the local certificate on the first visit.

Ask a question about indexed files:

~~~bash
trinaxai ask "Summarize my indexed project" --engine rag
~~~

If you skipped model downloads during setup, run `trinaxai setup` again when
you are ready. Use `trinaxai --help` to see every available command.

## Setup options

| Need | Command |
| --- | --- |
| Defer model downloads | `trinaxai setup --no-models` |
| Prepare without starting services | `trinaxai setup --no-start` |
| Choose a hardware profile | `trinaxai setup --profile 16gb` |
| Preview changes | `trinaxai setup --dry-run` |
| Automate setup | `trinaxai setup --non-interactive` |

The installer detects CPU, memory, GPU, and VRAM. The default profile is safe
for the detected machine. See [configuration](docs/CONFIGURATION.md) when you
need to tune models, resource limits, or providers.

## Daily commands

Use the CLI from any directory after setup:

| Goal | Command |
| --- | --- |
| Open the interactive assistant | `trinaxai chat` |
| Ask one question | `trinaxai ask "..." --engine rag` |
| Index a folder | `trinaxai index ./documents` |
| Run deep research | `trinaxai research --query "..." --depth 2` |
| Use the coding agent | `trinaxai agent --workspace .` |
| Check services | `trinaxai status` |
| Start or stop services | `trinaxai start` / `trinaxai stop` |
| Diagnose a problem | `trinaxai doctor --strict` |
| Update the installation | `trinaxai update` |
| Remove TrinaxAI | `trinaxai uninstall` |

## What TrinaxAI includes

- Local Ollama chat with task-aware routing for chat, code, reasoning, and math
- Hybrid RAG over code and documents with citations, collections, and incremental indexing
- Optional web search, deep research, memory, voice, and vision
- A sandboxed coding agent with approved workspaces and action approvals
- An HTTPS PWA for desktop and mobile with scoped device pairing
- A terminal interface for chat, indexing, research, diagnostics, and exports

## Models and hardware

Setup chooses a model profile from available memory and GPU resources:

| Profile | Chat and code | Fast responses | Embeddings |
| --- | --- | --- | --- |
| `8gb` | `qwen3.5:2b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `16gb` | `qwen3.5:4b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `32gb` | `qwen3.5:9b` | `qwen3.5:4b` | `qwen3-embedding:4b` |
| `64gb` | `qwen3.5:35b` / `qwen3-coder:30b` | `qwen3.5:4b` | `qwen3-embedding:4b` |

The `8gb` profile works with CPU-only hardware. See the
[configuration reference](docs/CONFIGURATION.md) for model and resource settings.

## Privacy and security

TrinaxAI binds local services to loopback by default. Ollama is not exposed as
a generic proxy. LAN browsers must pair with a one-time code and receive only
the capabilities you grant. Indexing, administration, agent tools, and model
management remain host-only.

Keep ports `3333` and `11434` private, protect `storage/.proxy_secret`, and
use a VPN instead of exposing the host to the public Internet. Read the
[security guide](docs/SECURITY.md) and [LAN pairing guide](docs/NETWORK_PAIRING.md)
before enabling another device.

## Documentation

| You want to… | Read |
| --- | --- |
| Install, update, or remove TrinaxAI | [Documentation hub](docs/README.md) |
| Configure models, RAG, networking, or limits | [Configuration](docs/CONFIGURATION.md) |
| Look up an environment variable | [Environment variables](docs/ENVIRONMENT_VARIABLES.md) |
| Use every CLI command | [CLI reference](docs/CLI_REFERENCE.md) |
| Understand the architecture | [Architecture](docs/ARCHITECTURE.md) |
| Integrate the HTTP API | [API reference](docs/API_REFERENCE.md) |
| Recover from an error | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Pair another device | [LAN pairing](docs/NETWORK_PAIRING.md) |
| Develop or contribute | [Developer guide](docs/DEVELOPER_GUIDE.md) |

The PWA also exposes these guides under **Settings → Documentation**.

## Development

This section is for contributors working from a source checkout. End users
should use the npm installation above.

~~~bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
(cd chat-pwa && npm ci && npm run dev)
~~~

Run `make check` before submitting a change. See the
[contributing guide](docs/CONTRIBUTING.md) for the full workflow.

## Screenshots

| Flow | English | Español |
| --- | --- | --- |
| Chat with citations | [Open](docs/assets/screenshots/chat-citations-en.png) | [Abrir](docs/assets/screenshots/chat-citations-es.png) |
| Indexing job | [Open](docs/assets/screenshots/indexing-job-en.png) | [Abrir](docs/assets/screenshots/indexing-job-es.png) |
| Pairing | [Open](docs/assets/screenshots/pairing-en.png) | [Abrir](docs/assets/screenshots/pairing-es.png) |
| Agent approval | [Open](docs/assets/screenshots/agent-approval-en.png) | [Abrir](docs/assets/screenshots/agent-approval-es.png) |

## License

TrinaxAI is licensed under AGPL-3.0-or-later. See [LICENSE](LICENSE) and the
[trademark guide](docs/TRADEMARK.md).

Built by [TrinaxCode](https://github.com/TrinaxCode) ·
[trinaxai.app](https://www.trinaxai.app/)
