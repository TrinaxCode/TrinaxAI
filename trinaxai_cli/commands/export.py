"""``trinaxai export`` — export a saved session as Markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trinaxai_cli.session import Session


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    name = getattr(args, "session", None) or "default"
    fmt = getattr(args, "format", "md") or "md"
    output = getattr(args, "output", None)
    try:
        records = Session.load(name)
    except Exception as exc:
        ui.error(f"Could not load session '{name}': {exc}")
        return 1
    if not records:
        ui.error(f"Session '{name}' is empty.")
        return 1

    lines = [f"# TrinaxAI session: {name}", ""]
    for r in records:
        role = r.get("role", "?")
        content = (r.get("content") or "").rstrip()
        ts = r.get("ts", 0)
        lines += [f"## {role}  ({ts})", "", content, ""]
    body = "\n".join(lines)

    out_path = Path(output).expanduser().resolve() if output else Path.cwd() / f"trinaxai-{name}.{fmt}"
    try:
        out_path.write_text(body, encoding="utf-8")
    except Exception as exc:
        ui.error(f"Could not write '{out_path}': {exc}")
        return 1
    ui.success(f"Exported {len(records)} record(s) → {out_path}")
    return 0
