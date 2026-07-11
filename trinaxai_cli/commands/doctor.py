"""``trinaxai doctor`` — quick local health check."""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

from trinaxai_cli.commands import _system


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    rows: list[list[str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        rows.append([name, "OK" if ok else "FAIL", detail])

    add("Python package", True, "CLI import works")
    root = _system.project_root()
    add("Install root", root is not None, str(root) if root else "set TRINAXAI_HOME or reinstall")
    add("Service manager", _system.service_manager().is_file(), str(_system.service_manager()))
    add("Ollama command", bool(shutil.which("ollama")), shutil.which("ollama") or "install Ollama")

    try:
        if root is None:
            raise FileNotFoundError("full TrinaxAI installation not found")
        status = subprocess.run(
            [sys.executable, str(_system.service_manager()), "status", "--base-dir", str(root)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        add("Services", status.returncode == 0, (status.stdout or status.stderr or "").strip().replace("\n", " | ")[:220])
    except Exception as exc:
        add("Services", False, str(exc))

    try:
        health = client.health()
        indexed = bool(health.get("indexed"))
        projects = health.get("projects", []) or []
        collections = health.get("collections", []) or []
        add("RAG API", True, client.base_url)
        add("Index built", indexed, "ready" if indexed else "run: trinaxai index .")
        add("Projects", True, str(len(projects)))
        add("Collections", True, ", ".join(c.get("id", "") for c in collections[:5]) or "none")
        try:
            stats = client.stats()
            add("Usage stats", True, f"messages={stats.get('messages_total', 0)} tokens={stats.get('tokens_estimated', 0)}")
        except Exception:
            pass
        try:
            mem = client.memory_summary()
            if mem.get("summary"):
                ui.panel(mem.get("summary", ""), title="Memory summary")
        except Exception:
            pass
    except Exception as exc:
        add("RAG API", False, f"{exc}; run: trinaxai start")

    ui.table(["check", "status", "detail"], rows, title="TrinaxAI doctor")
    return 0 if all(row[1] == "OK" for row in rows if row[0] in {"Python package", "Install root", "Service manager"}) else 1
