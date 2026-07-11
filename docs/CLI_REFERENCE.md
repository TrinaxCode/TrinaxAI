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
trinaxai --api-url https://localhost:3333 --insecure ask "Show index status"
```

| Global option | Purpose |
|---|---|
| `--api-url URL` | Override the RAG API URL. |
| `--install-root PATH` | Point to a full TrinaxAI installation. |
| `--insecure` | Disable TLS validation; use only for a known local certificate. |
| `--config PATH` | Load a specific TOML file. |
| `--no-color` | Disable ANSI colors. |
| `-v`, `--verbose` | Enable debug logging. |
| `--version` | Print the version. |

## Command map

```bash
trinaxai chat [--prompt TEXT] [--engine ollama|general|rag] [--collections IDS]
trinaxai ask PROMPT [--engine ollama|general|rag] [--collections IDS]
trinaxai research --query TEXT [--depth 1|2|3] [--collections IDS]
trinaxai index [PATH] [--collection ID] [--append]
trinaxai browse list-collections
trinaxai browse list-files [--collection ID]
trinaxai browse show-chunks --file PATH [--collection ID] [--limit N]
trinaxai memory list|add|forget|refresh|summary
trinaxai collections list|create|delete|use
trinaxai watch start|stop|status
trinaxai obsidian --vault PATH [--collection ID]
trinaxai export [--session NAME] [--format md] [--output PATH]
trinaxai status|start|stop|restart|models|config|doctor|version
trinaxai update
trinaxai uninstall
```

Use `--append` only when deleted source files should remain indexed. The watcher requires the server dependency `watchdog`. Markdown is currently the only export format. The `mcp` command is a placeholder and should not be used as a configured integration yet.

## Configuration file

Resolution order is `--config`, `TRINAXAI_CONFIG`, then the native platform path:

- Linux: `$XDG_CONFIG_HOME/trinaxai/config.toml` or `~/.config/trinaxai/config.toml`
- macOS: `~/Library/Application Support/TrinaxAI/config.toml`
- Windows: `%APPDATA%\TrinaxAI\config.toml`

```toml
[api]
base_url = "https://localhost:3333"
verify_tls = false

[defaults]
engine = "ollama"
model = "qwen2.5-coder:3b"
collections = ["default"]

[ui]
color = "auto"

[session]
enabled = false
dir = ""
```

Exit codes are `0` for success, `1` for a command/service/configuration error, and `130` for `Ctrl+C`. For diagnostics, run `trinaxai --verbose doctor` and see the [developer guide](DEVELOPER_GUIDE.md).

