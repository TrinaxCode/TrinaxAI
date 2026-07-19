"""TrinaxAI CLI entry point.

Builds the top-level argparse tree, loads local config, constructs the
HTTP client and UI console, and dispatches to the requested subcommand.

Subcommand modules live in :mod:`trinaxai_cli.commands` and are imported
lazily by :func:`_dispatch` so that ``--help`` stays fast and partial
installs (one command's deps missing) do not break the others.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from trinaxai_cli.config import CLIConfig
from trinaxai_cli.ui import get_console

LOG = logging.getLogger("trinaxai_cli")
VERSION = "1.2.0"


# ----------------------------------------------------------------- argparse


def _build_parser() -> argparse.ArgumentParser:
    """Return the top-level argparse parser with all subcommands wired in."""
    parser = argparse.ArgumentParser(
        prog="trinaxai",
        description=(
            "TrinaxAI CLI — local-first terminal assistant. The default command opens a "
            "unified REPL that auto-routes between chat, web search, deep research, the "
            "private local coding agent and RAG."
        ),
    )
    parser.add_argument("--api-url", help="RAG API base URL (overrides config).")
    parser.add_argument("--install-root", help="Full TrinaxAI installation directory (overrides auto-discovery).")
    parser.add_argument(
        "--config",
        help="Path to config TOML (overrides $TRINAXAI_CONFIG and XDG search).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour output.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose (DEBUG) logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"TrinaxAI CLI {VERSION}",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Flat (no sub-subcommands) commands
    chat_p = sub.add_parser("chat", help="Unified REPL (chat · web · research · agent · RAG) or single prompt.")
    chat_p.add_argument("--prompt", help="Run a single prompt and exit.")
    chat_p.add_argument("--session", help="Session name. A unique name is created when omitted.")
    chat_p.add_argument("--collections", help="Comma-separated collection ids.")
    chat_p.add_argument(
        "--engine",
        choices=["general", "ollama", "rag"],
        help="Chat engine. General uses Ollama without indexed-document context.",
    )
    chat_p.add_argument("--workspace", help="Agent workspace root for /agent turns (default: current dir).")

    ask_p = sub.add_parser("ask", help="Ask one question and exit.")
    ask_p.add_argument("prompt", nargs="*", help="Question to send, or omit it to read UTF-8 text from stdin.")
    ask_p.add_argument("--session", help="Session name. A unique name is created when omitted.")
    ask_p.add_argument("--collections", help="Comma-separated collection ids.")
    ask_p.add_argument("--engine", choices=["general", "ollama", "rag"])

    agent_p = sub.add_parser(
        "agent",
        help="Agentic assistant: read, write and run code in a workspace.",
    )
    agent_p.add_argument("--prompt", help="Run a single task and exit.")
    agent_p.add_argument("--workspace", help="Directory the agent operates in (default: current dir).")
    agent_p.add_argument("--model", help="Ollama model to use (default: the tool-calling coder model).")
    agent_p.add_argument("--session", help="Session name. A unique name is created when omitted.")
    agent_p.add_argument("--max-steps", dest="max_steps", type=int, help="Max tool-use iterations (default: 25).")
    agent_p.add_argument(
        "--yolo",
        action="store_true",
        help="Auto-approve every action without confirmation (dangerous).",
    )

    idx_p = sub.add_parser("index", help="Index a folder into the local RAG store.")
    idx_p.add_argument("path", nargs="?", help="Folder to index, for example: trinaxai index .")
    idx_p.add_argument("--folder", help="Folder to index (legacy alias).")
    idx_p.add_argument("--collection", default="default", help="Collection id.")
    idx_p.add_argument("--append", action="store_true", help="Append-only (don't remove deleted files).")

    browse_p = sub.add_parser("browse", help="Browse collections, files and chunks.")
    browse_sub = browse_p.add_subparsers(dest="browse_command", metavar="ACTION")
    browse_sub.add_parser("list-collections", help="List all collections.")
    blf = browse_sub.add_parser("list-files", help="List files in a collection.")
    blf.add_argument("--collection", default="default")
    bsc = browse_sub.add_parser("show-chunks", help="Show chunks for a file.")
    bsc.add_argument("--collection", default="default")
    bsc.add_argument("--file", required=True)
    bsc.add_argument("--limit", type=int, default=50)

    res_p = sub.add_parser("research", help="Multi-pass deep research query.")
    res_p.add_argument("--query", required=True)
    res_p.add_argument("--collections", help="Comma-separated collection ids.")
    res_p.add_argument("--depth", type=int, default=2, choices=[1, 2, 3])

    sub.add_parser("status", help="Show local service status.")
    sub.add_parser("start", help="Start TrinaxAI local services.")
    stop_p = sub.add_parser("stop", help="Stop AI services and keep them off after reboot.")
    stop_p.add_argument("--all", action="store_true", help="Also stop the PWA frontend.")
    stop_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation.")
    restart_p = sub.add_parser("restart", help="Restart TrinaxAI local services.")
    restart_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation.")
    sub.add_parser("models", help="List installed and recommended local models.")
    pair_p = sub.add_parser("pair", help="Pair and manage trusted LAN devices.")
    pair_sub = pair_p.add_subparsers(dest="pair_command", metavar="ACTION")
    pair_start = pair_sub.add_parser("start", help="Generate a short, one-time pairing code.")
    pair_start.add_argument(
        "--scopes",
        default="chat,read_private",
        help="Comma-separated scopes granted to the device.",
    )
    pair_start.add_argument("--ttl", type=int, default=300, help="Code lifetime in seconds (60-900).")
    pair_start.add_argument("--device-ttl-days", type=int, help="Optional device credential lifetime.")
    pair_start.add_argument("--pwa-url", help="PWA origin used in the displayed pairing link.")
    pair_sub.add_parser("list", help="List paired and revoked devices.")
    pair_revoke = pair_sub.add_parser("revoke", help="Revoke one paired device.")
    pair_revoke.add_argument("device_id", help="Device id shown by 'trinaxai pair list'.")
    sub.add_parser("config", help="Show active CLI and environment configuration.")
    doctor_p = sub.add_parser("doctor", help="Run local health checks.")
    doctor_p.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when any critical health check fails.",
    )
    doctor_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human table.",
    )
    sub.add_parser("version", help="Print TrinaxAI CLI version.")
    sub.add_parser("help", help="Show TrinaxAI CLI help.")
    update_p = sub.add_parser("update", help="Update code, dependencies and the PWA.")
    update_p.add_argument("-y", "--yes", action="store_true", help="Use safe non-interactive defaults.")
    update_p.add_argument("--no-backup", action="store_true")
    update_p.add_argument("--no-pull", action="store_true")
    update_p.add_argument("--models", action="store_true", help="Update configured Ollama models.")
    update_p.add_argument("--no-models", action="store_true")
    update_p.add_argument("--restart", action="store_true")
    update_p.add_argument("--no-restart", action="store_true")

    uninstall_p = sub.add_parser("uninstall", help="Guided, safe TrinaxAI uninstaller.")
    uninstall_p.add_argument("-y", "--yes", action="store_true", help="Confirm and use safe defaults.")
    uninstall_p.add_argument("--purge", action="store_true", help="Also remove data, models, certs and Ollama.")
    uninstall_p.add_argument("--remove-data", action="store_true")
    uninstall_p.add_argument("--remove-models", action="store_true")
    uninstall_p.add_argument("--remove-ollama", action="store_true")
    uninstall_p.add_argument("--keep-env", action="store_true")
    # Keep the reserved command parseable for compatibility, but do not
    # advertise an integration that does not exist yet.
    sub.add_parser("mcp", help=argparse.SUPPRESS)
    exp_p = sub.add_parser("export", help="Export a saved session.")
    exp_p.add_argument("--session", default="default")
    exp_p.add_argument("--format", default="md", choices=["md"])
    exp_p.add_argument("--output", help="Output file path.")

    obs_p = sub.add_parser("obsidian", help="Import an Obsidian vault into a collection.")
    obs_p.add_argument("--vault", required=True, help="Path to the Obsidian vault root.")
    obs_p.add_argument("--collection", default="obsidian", help="Target collection id.")

    # watch (start | stop | status)
    watch_p = sub.add_parser("watch", help="File watcher daemon control.")
    watch_sub = watch_p.add_subparsers(dest="watch_command", metavar="ACTION")
    ws = watch_sub.add_parser("start", help="Start the watcher.")
    ws.add_argument("--paths", nargs="+", help="Directories to watch.")
    ws.add_argument("--collection", help="Restrict to a single collection path.")
    watch_sub.add_parser("stop", help="Stop the watcher.")
    watch_sub.add_parser("status", help="Show watcher status.")

    # memory (list | add | forget | refresh | summary)
    mem_p = sub.add_parser("memory", help="Memory store management.")
    mem_sub = mem_p.add_subparsers(dest="memory_command", metavar="ACTION")
    mem_sub.add_parser("list", help="List memories.")
    ma = mem_sub.add_parser("add", help="Add a memory.")
    ma.add_argument("--text", help="Memory text (else prompted).")
    ma.add_argument("--tags", help="Comma-separated tags.")
    mf = mem_sub.add_parser("forget", help="Forget a memory by id (prefix ok).")
    mf.add_argument("memory_id_positional", nargs="?", help="Memory id or prefix.")
    mf.add_argument("--memory-id", dest="memory_id", help="Memory id or prefix.")
    mem_sub.add_parser("refresh", help="Refresh the memory index.")
    mem_sub.add_parser("summary", help="Show the current summary.")

    # collections (list | create | delete | use)
    col_p = sub.add_parser("collections", help="Collection management.")
    col_sub = col_p.add_subparsers(dest="collections_command", metavar="ACTION")
    col_sub.add_parser("list", help="List collections.")
    cc = col_sub.add_parser("create", help="Create a collection.")
    cc.add_argument("--name", help="Collection name.")
    cd = col_sub.add_parser("delete", help="Delete a collection.")
    cd.add_argument("--collection-id", dest="collection_id", help="Collection id.")
    cd.add_argument("--name", help="Exact collection name (must be unique).")
    cu = col_sub.add_parser("use", help="Switch the active collection.")
    cu.add_argument("--collection-id", dest="collection_id", help="Collection id.")

    return parser


# ------------------------------------------------------------- dispatcher


def _dispatch(name: str, args: Any, client: Any, ui: Any, config: CLIConfig) -> int:
    """Lazy-import ``trinaxai_cli.commands.<name>`` and call its ``run``."""
    module_name = f"trinaxai_cli.commands.{name}"
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        ui.error(f"command '{name}' not yet implemented (import: {exc})")
        return 1
    run_fn = getattr(module, "run", None)
    if run_fn is None:
        ui.error(f"command '{name}' not yet implemented (no run() function).")
        return 1
    try:
        result = run_fn(args, client, ui, config)
    except KeyboardInterrupt:
        ui.warn("interrupted.")
        return 130
    except SystemExit as exc:
        # Subcommands are allowed to SystemExit directly.
        return int(exc.code) if exc.code is not None else 0
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        LOG.exception("command %s raised an exception", name)
        ui.error(f"command '{name}' failed: {exc}")
        return 1
    try:
        return int(result)
    except (TypeError, ValueError):
        return 0 if result is None else 1


# ------------------------------------------------------------------ main


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point.  Returns the process exit code."""
    invocation_cwd = str(Path.cwd().resolve())
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Preserve where the person invoked TrinaxAI before config/imports or an
    # installation wrapper can change process context.
    setattr(args, "invocation_cwd", invocation_cwd)

    if args.install_root:
        os.environ["TRINAXAI_HOME"] = str(Path(args.install_root).expanduser())

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # 1. Load config (CLI flag > $TRINAXAI_CONFIG > XDG; falls back to defaults).
    config_path = Path(args.config).expanduser() if args.config else None
    if config_path is None:
        config_path = CLIConfig.find_config()
    config = CLIConfig.load(config_path) if config_path else CLIConfig.load()

    # 2. Resolve effective api_url and verify_tls.
    api_url = args.api_url or config.api["base_url"]
    verify_tls = bool(config.api.get("verify_tls", True))

    # 3. Build UI console (honours --no-color, $NO_COLOR, config.ui.color).
    no_color = bool(args.no_color) or (str(config.ui.get("color", "auto")) == "never")
    ui = get_console(no_color=no_color)

    # 4. Build HTTP client (lazy import keeps --help cheap).
    from trinaxai_cli.client import TrinaxAPIClient

    client = TrinaxAPIClient(base_url=api_url, verify_tls=verify_tls)

    # 5. Dispatch (default = chat REPL).
    name = args.command or "chat"
    try:
        return _dispatch(name, args, client, ui, config)
    finally:
        client.close()
