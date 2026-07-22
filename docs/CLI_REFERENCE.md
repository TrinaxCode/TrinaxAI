# TrinaxAI CLI Reference

The `trinaxai` CLI provides direct Ollama chat, RAG queries, indexing, memory and collection management, and service control. It requires Python 3.10 or newer.

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
| `-v`, `--verbose` | Enable debug logging. |
| `--version` | Print the version. |

## Command map

```bash
trinaxai chat [--prompt TEXT] [--engine ollama|general|rag] [--collections IDS]
trinaxai ask PROMPT [--engine ollama|general|rag] [--collections IDS]
trinaxai agent [--prompt TEXT] [--workspace PATH] [--model NAME] [--max-steps N] [--yolo]
trinaxai research --query TEXT [--depth 1|2|3] [--collections IDS]
trinaxai index [PATH] [--collection ID] [--append]
trinaxai browse list-collections
trinaxai browse list-files [--collection ID]
trinaxai browse show-chunks --file PATH [--collection ID] [--limit N]
trinaxai memory list|add|forget|refresh|summary
trinaxai collections list|create|delete|use
trinaxai watch start|stop|status
trinaxai pair [start] [--scopes LIST] [--ttl SECONDS] [--device-ttl-days DAYS] [--pwa-url URL]
trinaxai pair list
trinaxai pair revoke DEVICE_ID
trinaxai obsidian --vault PATH [--collection ID]
trinaxai export [--session NAME] [--format md] [--output PATH]
trinaxai status|start|stop|restart|models|config|doctor [--strict] [--json]|version
trinaxai update
trinaxai uninstall
```

Use `--append` only when deleted source files should remain indexed. Each root
has an independent stable `source_id`, so syncing another root into the same
collection no longer replaces namesake paths from the first. The watcher
requires the server dependency `watchdog`. Markdown is currently the only
export format. MCP is not an advertised/usable command in this release.

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
| `/index [PATH]` | Index a folder. |
| `/memory` | List persistent memories. |
| `/collections` | List indexed collections. |
| `/watch` | Show watcher status. |
| `/status` | Show service status. |

## Pairing LAN devices

Run pairing creation and device administration on the host (or with the admin
super-credential):

```bash
trinaxai pair start
trinaxai pair start --scopes chat,read_private,index --ttl 180 --device-ttl-days 30
trinaxai pair list
trinaxai pair revoke DEVICE_ID
```

`pair` without an action is the same as `pair start`. It prints a single-use
code and a PWA link. Codes last 60–900 seconds (`300` by default). The default
device scopes are `chat,read_private`; available elevated scopes are `index`,
`system`, `agent`, and `web`. `agent_yolo` is reserved for local policy and never makes
remote HTTP tool calls auto-approve.

The browser stores its returned bearer in `localStorage` to retain its revocable
device identity across restarts. A packaged CLI
acting as a paired remote device reads `TRINAXAI_DEVICE_TOKEN` and sends
`X-TrinaxAI-Device-Token`; point `--api-url` at the gateway RAG base, for example
`https://host:3334/api/rag`. Do not put a token in command history or a committed
TOML file. Pairing represents a revocable device capability, not a user account.

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

[ui]
color = "auto"

[session]
enabled = false
dir = ""
```

Exit codes are `0` for success, `1` for a command/service/configuration error,
and `130` for `Ctrl+C`. Human `doctor` remains a diagnostic report; automation
should run `trinaxai doctor --strict --json`, which emits one JSON document and
returns nonzero when a critical check fails. See the
[developer guide](DEVELOPER_GUIDE.md).
