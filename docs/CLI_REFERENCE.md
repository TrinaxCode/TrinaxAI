<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 💻 CLI Reference
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.4.1"><img src="https://img.shields.io/badge/version-1.4.1-006bbd" alt="Stable release: 1.4.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="CLI_REFERENCE.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The `trinaxai` CLI provides direct Ollama chat, RAG queries, indexing, memory and collection management, and service control. End users receive it through the npm installation. The source-checkout command below is for contributors and development. For symptom-based recovery, see the [troubleshooting guide](TROUBLESHOOTING.md).

## Installation and help

```bash
python -m pip install -e .
trinaxai --help
trinaxai help
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
trinaxai agent [TASK ...] [-p TEXT] [--workspace PATH] [--model NAME] [--max-steps N]
               [--permission-mode MODE] [--output-format text|json] [-c | -r SESSION] [--yolo]
trinaxai research TEXT|--query TEXT [--web] [--session NAME] [--depth DEPTH] [--collections IDS] [--thinking]
trinaxai index [PATH] [--collection ID] [--append]
trinaxai browse list-collections
trinaxai browse list-files [--collection ID]
trinaxai browse show-chunks --file PATH [--collection ID] [--limit N]
trinaxai memory ACTION
trinaxai collections ACTION
trinaxai watch ACTION
trinaxai pair [start] [--scopes LIST] [--ttl SECONDS] [--device-ttl-days DAYS] [--pwa-url URL]
trinaxai pair list
trinaxai pair set DEVICE_ID --scopes LIST
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
trinaxai network off
trinaxai update
trinaxai uninstall
```

`ENGINE` is `general`, `ollama`, or `rag`; `DEPTH` is `1`, `2`, or `3`.
`--no-thinking` is the inverse of `--thinking`. The command map shows the
common shape; run `trinaxai COMMAND --help` for every flag and default.

`trinaxai stop --all` stops the PWA and the rest of the stack, then leaves only
the loopback recovery page at `https://localhost:3334`; LAN access stays closed
until TrinaxAI is started from that local page.

Use `--append` only when deleted source files should remain indexed. Each root
has an independent stable `source_id`, so syncing another root into the same
collection no longer replaces namesake paths from the first. The watcher
requires the server dependency `watchdog`. Session export supports Markdown,
PDF, and Word (`docx`, also accepted as `word`) while retaining public
DeepResearch metadata and sources. The reserved `trinaxai mcp` command returns
exit code `2` and does not start an MCP server in this release; use the HTTP API
or the supported CLI commands instead.

## Chat and queries

```bash
trinaxai chat
trinaxai chat --prompt "Summarize this project" --engine rag --collections default,docs --thinking
trinaxai chat --file ./photo.png --prompt "Describe this image"
trinaxai ask --file ./manual.pdf "Summarize this document"
trinaxai ask "Write a test for this function" --engine ollama --no-thinking
trinaxai agent --workspace . --prompt "Fix the tests"
trinaxai research --query "Compare the security modules" --session security --depth 2 --collections default --thinking
```

In automatic chat mode, TrinaxAI routes each turn by capability: direct public lookups go to web search, questions about your own projects or files go to RAG, and complex multi-source requests go to deep research. Agent execution is explicit: use `/agent` (or `trinaxai agent`) before asking it to write files. Use `/chat`, `/web`, `/research`, `/rag`, or `/agent` when you want to pin a mode.

`--engine general` is an alias of direct Ollama chat; `rag` uses indexed documents. `--collections` accepts comma-separated IDs.

Use `trinaxai chat --file PATH --prompt "Describe this"` to analyze one local
image or text/document file. The attachment path is validated locally and the
file is not uploaded by the CLI.

Without `--web`, `research` works from your indexed documents (and searches the web only when the question asks for current information); `--web` always grounds it on web search, which sends the question to the search provider. `research` lets the server choose whether to reason (fast for a quick web lookup); `--thinking` / `--no-thinking` force it, and the config's `defaults.thinking` applies to `chat` and `ask` only. `research` tries to read bounded page text (`full_page`) and keeps the search
excerpt as a fallback (`snippet_only`); the sources say which one was used. Add `--session NAME` to save the question, answer,
public research metadata, and sources for a later `trinaxai export`.

## Indexing and exploration

```bash
trinaxai index . --collection default
trinaxai index ~/Documents --collection documents --append
trinaxai browse list-collections
trinaxai browse list-files --collection default
trinaxai browse show-chunks --collection default --file README.md --limit 20
trinaxai obsidian --vault ~/Notes --collection notes
```

Use `--append` to keep files that no longer exist on disk. Without it, the
command synchronizes the selected root. Each root has an independent stable
`source_id`, so matching paths from another root do not replace the first root.

## Memory and collections

```bash
trinaxai memory list
trinaxai memory add --text "I prefer concise answers" --tags preference,style
trinaxai memory forget --memory-id MEMORY_ID
trinaxai memory refresh
trinaxai memory summary

trinaxai collections list
trinaxai collections create --name "Documentation"
trinaxai collections use --collection-id documentation
trinaxai collections delete --collection-id documentation
```

## Watcher and export

```bash
trinaxai watch start --paths ~/projects/app --collection default
trinaxai watch status
trinaxai watch stop
trinaxai export --session SESSION --format md --output conversation
```

The watcher requires the `watchdog` server dependency. Session export supports
Markdown, PDF, and Word formats while retaining public research metadata,
sources, and citations.

## Lifecycle and diagnostics

```bash
trinaxai status
trinaxai start
trinaxai restart
trinaxai stop
trinaxai stop --all
trinaxai models
trinaxai config
trinaxai doctor
trinaxai doctor --strict --json
trinaxai update
trinaxai uninstall
```

`trinaxai stop --all` stops the PWA and the rest of the stack. Only the local
recovery page remains at `https://localhost:3334`, and LAN access stays closed
until TrinaxAI starts again.

Read `trinaxai update --help` and `trinaxai uninstall --help` before automating
maintenance. `uninstall --purge` can remove data, models, certificates, and
Ollama. The reserved `trinaxai mcp` command exits with code `2` and does not
start an MCP server in this release.

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
trinaxai pair set DEVICE_ID --scopes chat,read_private,agent
trinaxai pair revoke DEVICE_ID
```

`pair` without an action is the same as `pair start`. It prints a single-use
code and a PWA link. Codes last 60–900 seconds (`300` by default). The default
device scopes are `chat,read_private`. Optional additional scopes are `web` and
the elevated `index`, `agent` and `modify`, which let that device change the
host (the CLI warns when you grant one). `pair set` replaces the permissions of
an existing device. `system` and `agent_yolo` can never be granted and are
rejected even when an admin credential is sent from LAN.

The browser keeps new pairing credentials in an `HttpOnly; SameSite=Strict`
cookie scoped to `/api`. A packaged CLI acting as a paired remote device
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

`trinaxai network` also says whether other devices may reach TrinaxAI. If you
allowed that and change your mind, run `trinaxai network off` to keep it on this
computer only (it restarts the web app); `trinaxai network refresh` allows it again.

## Agent workflow

`trinaxai agent` follows the same workflow as other terminal coding agents.

```bash
trinaxai agent                                 # interactive session
trinaxai agent "add a --verbose flag to cli.py"  # one task, answer only on stdout
echo "explain this repo" | trinaxai agent -p     # task from stdin
trinaxai agent -p "fix the failing test" --output-format json
trinaxai agent --continue                      # resume the latest session
trinaxai agent --permission-mode plan          # read-only: ask for a plan first
```

| Feature | Behavior |
|---|---|
| Transcript | `● read_file(app.py)` followed by `⎿ Read 120 lines`; shell output is folded to 8 lines; a `✻ 12.3s · 3 tool calls · 90 tokens` footer closes each turn. |
| Approvals | Edits show a real unified diff, commands show the command. Choose **Yes**, **Yes, and don't ask again** (edits for the session, or a command: read-only ones (`git status/diff/log/show`, `ls`, `cat`, `pytest`, …) are remembered by name, any other command only verbatim; compound commands with `;`, `\|`, `&&` or `$(…)` are never remembered) or **No**. |
| Permission modes | `default` asks, `accept-edits` auto-approves file edits, `plan` blocks every change, `yolo` approves everything. `Shift+Tab` cycles the first three; `/mode` and `--permission-mode` set any. |
| Without a terminal | Dangerous actions are refused unless you pass `--permission-mode accept-edits` or `--yolo`. |
| `@path` | Attaches a workspace file or directory listing to the prompt (Tab completes). Paths outside the workspace are ignored. |
| Todo list | The model keeps a visible checklist for multi-step work (`todo_write`; `/todos`). |
| Project instructions | `TRINAXAI.md`, `AGENTS.md` and `CLAUDE.md` at the workspace root are added to the system prompt (8,000 characters in total). `/init` asks the agent to write `TRINAXAI.md`. |
| Interrupt | `Ctrl-C` stops the running turn and rolls the conversation back; press `↑` to edit and resend. |
| Input | History persists in `~/.local/share/trinaxai/agent_history`; `Alt+Enter` or a trailing `\` adds a newline; the bottom bar shows model, workspace, mode and context use. |
| Slash commands | `/help /clear /compact /model /mode /yolo /tools /status /todos /diff /init /resume /exit`. |
| JSON output | `--output-format json` prints `result`, `status` (`complete` or `degraded`), `session`, `model`, `tool_calls`, `duration_s` and `tokens`. |

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
model = ""  # empty = automatic: the model chosen for this computer
collections = ["default"]
thinking = true

[ui]
color = "auto"

[session]
enabled = false
dir = ""
```

## Exit codes

- `0`: success.
- `1`: command, service, network, or configuration error.
- `130`: interrupted with `Ctrl+C`.

Human `doctor` remains a diagnostic report; automation
should run `trinaxai doctor --strict --json`, which emits one JSON document and
returns nonzero when a critical check fails. See the [troubleshooting guide](TROUBLESHOOTING.md)
and [developer guide](DEVELOPER_GUIDE.md). `update` and `uninstall` can change
installed files or remove data; read their `--help` output before automating
them.

On a fresh installation with no user folder indexed yet, the human doctor
report shows `Index built` as `INFO` and explains how to run `trinaxai index .`;
this is expected setup state, not a service failure.
