<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 💻 CLI Reference
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="CLI_REFERENCE.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The `trinaxai` CLI provides direct Ollama chat, RAG queries, indexing, memory and collection management, and service control. It requires Python 3.10 or newer. For symptom-based recovery, see the [troubleshooting guide](TROUBLESHOOTING.md).

## Installation and help

```bash
python -m pip install -e .
trinaxai --help
trinaxai COMMAND --help
```

Running `trinaxai` without a subcommand opens interactive chat. Global options must precede the subcommand:

```bash
trinaxai --api-url https://localhost:3333 --ca-file /path/to/rootCA.pem ask "Show index status"
```

| Global option | Purpose |
|---|---|
| `--api-url URL` | Override the RAG API URL. |
| `--ca-file PATH` | Trust an explicit CA bundle while keeping HTTPS verification enabled. |
| `--install-root PATH` | Point to a full TrinaxAI installation. |
| `--config PATH` | Load a specific TOML file. |
| `--no-color` | Disable ANSI colors. |
| `--language LANG`, `--lang LANG` | Select `en` or `es` for human-facing CLI output; also supports `TRINAXAI_LANG` and `ui.language` in TOML. |
| `-v`, `--verbose` | Enable debug logging. |
| `--version` | Print the version. |

## Command map

```bash
trinaxai chat [--prompt TEXT] [--file PATH] [--engine ENGINE] [--collections IDS] [--thinking]
trinaxai ask [PROMPT ...] [--file PATH] [--engine ENGINE] [--collections IDS] [--thinking]
trinaxai agent [--prompt TEXT] [--workspace PATH] [--model NAME] [--max-steps N] [--yolo]
trinaxai research --query TEXT [--session NAME] [--depth DEPTH] [--collections IDS] [--thinking]
trinaxai index [PATH] [--collection ID] [--append]
trinaxai browse list-collections
trinaxai browse list-files [--collection ID]
trinaxai browse show-chunks --file PATH [--collection ID] [--limit N]
trinaxai memory ACTION
trinaxai collections ACTION
trinaxai watch ACTION
trinaxai pair [start] [--scopes LIST] [--ttl SECONDS] [--device-ttl-days DAYS] [--pwa-url URL]
trinaxai pair list
trinaxai pair revoke DEVICE_ID
trinaxai obsidian --vault PATH [--collection ID]
trinaxai export [--session NAME] [--format FORMAT] [--output PATH]
trinaxai status
trinaxai start
trinaxai restart
trinaxai models
trinaxai config
trinaxai doctor
trinaxai version
trinaxai stop
trinaxai stop --all
trinaxai network
trinaxai network refresh
trinaxai update
trinaxai uninstall
```

`ENGINE` is `general`, `ollama`, or `rag`; `DEPTH` is `1`, `2`, or `3`.
`--no-thinking` is the inverse of `--thinking`. The command map shows the
common shape; run `trinaxai COMMAND --help` for every flag and default.

`trinaxai stop --all` stops the PWA and the rest of the stack, then leaves only
the loopback recovery page at `https://localhost:3334`; LAN access stays closed
until TrinaxAI is started from that local page.

Use `trinaxai chat --file PATH --prompt "Describe this"` to analyze one local
image or text/document file. The attachment path is validated locally and the
file is not uploaded by the CLI.

In automatic chat mode, TrinaxAI routes each turn by capability: direct public lookups go to web search, questions about your own projects or files go to RAG, and complex multi-source requests go to deep research. Agent execution is explicit: use `/agent` (or `trinaxai agent`) before asking it to write files. Use `/chat`, `/web`, `/research`, `/rag`, or `/agent` when you want to pin a mode.

Add `--session NAME` to `trinaxai research` to save the question, answer,
public research metadata, and sources for a later `trinaxai export`.

Use `--append` only when deleted source files should remain indexed. Each root
has an independent stable `source_id`, so syncing another root into the same
collection no longer replaces namesake paths from the first. The watcher
requires the server dependency `watchdog`. Session export supports Markdown,
PDF, and Word (`docx`, also accepted as `word`) while retaining public
DeepResearch metadata and sources. The reserved `trinaxai mcp` command returns
exit code `2` and does not start an MCP server in this release; use the HTTP API
or the supported CLI commands instead.

## Interactive slash commands

Inside `trinaxai` or `trinaxai chat`, type `/` to display the menu. The registry
currently exposes:

| Command | Purpose |
|---|---|
| `/help` | Show the slash-command menu. |
| `/exit`, `/quit` | Leave interactive chat. |
| `/clear` | Clear the in-memory conversation. |
| `/chat`, `/general`, `/ollama` | Pin isolated general chat. |
| `/agent [task]` | Pin the tool-using agent and optionally run a task. |
| `/web [query]` | Pin a web-grounded answer. |
| `/research [query]` | Pin multi-pass deep research. |
| `/rag [collection]` | Use an indexed collection. |
| `/auto` | Restore automatic routing for every turn. |
| `/model [NAME MODE]` | Select an installed model and Ollama/RAG mode. |
| `/workspace [PATH]` | Set the agent workspace. |
| `cd [PATH]` | Change the session directory; relative paths start from the current directory. |
| `/yolo` | Toggle dangerous agent auto-approval. |
| `/thinking on|off` | Enable or disable efficient provider reasoning. It still skips simple turns. |
| `/index [PATH]` | Index a folder. |
| `/memory` | List persistent memories. |
| `/collections` | List indexed collections. |
| `/watch` | Show watcher status. |
| `/status` | Show service status. |

## Pairing LAN devices

Run pairing creation and device administration from the host through loopback:

```bash
trinaxai pair start
trinaxai pair start --scopes chat,read_private,web --ttl 180 --device-ttl-days 30
trinaxai pair list
trinaxai pair revoke DEVICE_ID
```

`pair` without an action is the same as `pair start`. It prints a single-use
code and a PWA link. Codes last 60–900 seconds (`300` by default). The default
device scopes are `chat,read_private`; `web` is the only optional additional
scope. `index`, `system`, `agent`, and `agent_yolo` are retired for paired
devices and are rejected even when an admin credential is sent from LAN.

The browser keeps new pairing credentials in an `HttpOnly; SameSite=Strict`
cookie scoped to `/api/rag`. A packaged CLI acting as a paired remote device
reads `TRINAXAI_DEVICE_TOKEN` and sends `X-TrinaxAI-Device-Token`; the API never
copies that header into a response cookie. Point `--api-url` at the gateway RAG base, for example
`https://host:3334/api/rag`. Do not put a token in command history or a committed
TOML file. Pairing represents a revocable device capability, not a user account.

## Changing local networks

`trinaxai network` prints the current IP PWA link and a `.local` alternative.
After changing Wi-Fi, router, or LAN address, run `trinaxai network refresh` on
the host to renew HTTPS, CORS, and the active service configuration. This does
not erase data or grant every device access; existing pairing scopes remain in
force.

## Agent isolation

`trinaxai agent` confines file operations to `--workspace` after resolving
symlinks. Dangerous write/edit/terminal tools ask for approval unless the local
operator explicitly passes `--yolo`. On Linux, terminal commands require
bubblewrap, have no network, see the workspace as the only writable host tree,
and are terminated as a process group on timeout. On macOS/Windows or a Linux
host without bubblewrap, terminal execution fails closed. The compatibility
escape hatch `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1` grants full
user-level host access and should not be used on remotely reachable services.

HTTP agent workspaces are separately restricted by
`TRINAXAI_AGENT_WORKSPACE_ROOTS`; HTTP yolo is disabled by default and cannot be
used from a non-loopback client.

`research` can return bounded page text (`full_page`) or fall back to a search
excerpt (`snippet_only`); the source metadata says which one was used.

## Configuration file

Resolution order is `--config`, `TRINAXAI_CONFIG`, then the native platform path:

- Linux: `$XDG_CONFIG_HOME/trinaxai/config.toml` or `~/.config/trinaxai/config.toml`
- macOS: `~/Library/Application Support/TrinaxAI/config.toml`
- Windows: `%APPDATA%\TrinaxAI\config.toml`

```toml
[api]
base_url = "https://localhost:3333"
verify_tls = true

[defaults]
engine = "ollama"
model = "qwen3.5:2b"
collections = ["default"]
thinking = true

[ui]
color = "auto"

[session]
enabled = false
dir = ""
```

Exit codes are `0` for success, `1` for a command/service/configuration error,
and `130` for `Ctrl+C`. Human `doctor` remains a diagnostic report; automation
should run `trinaxai doctor --strict --json`, which emits one JSON document and
returns nonzero when a critical check fails. See the [troubleshooting guide](TROUBLESHOOTING.md)
and [developer guide](DEVELOPER_GUIDE.md). `update` and `uninstall` can change
installed files or remove data; read their `--help` output before automating
them.
