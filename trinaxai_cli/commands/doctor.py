"""``trinaxai doctor`` — quick local health check."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

from trinaxai_cli.commands import _system
from trinaxai_cli.processes import run_process_group
from trinaxai_core import normalize_http_base_url


def _process_command(pid: int | None) -> str:
    """Best-effort command line lookup without mutating the inspected process."""
    if not pid or pid <= 0:
        return ""
    proc_path = f"/proc/{pid}/cmdline"
    try:
        with open(proc_path, "rb") as stream:
            return stream.read(64 * 1024).replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        pass
    if os.name == "nt":
        return ""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _frontend_mode_from_command(command: str) -> str | None:
    normalized = " ".join(command.lower().split())
    if "vite preview" in normalized or "npm run preview" in normalized:
        return "preview"
    if ("vite" in normalized and "--host" in normalized) or "npm run dev" in normalized:
        return "dev"
    return None


def _safe_backend_command(command: str) -> bool | None:
    normalized = " ".join(command.lower().split())
    if not normalized:
        return None
    if "--host 0.0.0.0" in normalized or "--host ::" in normalized:
        return False
    if "--host 127." in normalized or "--host localhost" in normalized or "--host ::1" in normalized:
        return True
    return None


def _find_ollama() -> str | None:
    candidates = [
        shutil.which("ollama"),
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
        "/snap/bin/ollama",
        "/opt/homebrew/bin/ollama",
        os.path.expanduser("~/bin/ollama"),
        os.path.expanduser("~/.ollama/bin/ollama"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _ollama_api_ok(base_url: str = "http://127.0.0.1:11434") -> bool:
    base_url = normalize_http_base_url(base_url)
    if not base_url:
        return False
    try:
        # base_url is restricted to HTTP(S) with a host above.
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=3) as response:  # nosec B310
            return 200 <= int(response.status) < 300
    except (OSError, urllib.error.URLError, ValueError):
        return False


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, *, critical: bool = False) -> None:
        checks.append({"check": name, "ok": ok, "critical": critical, "detail": detail})

    add("Python package", True, "CLI import works", critical=True)
    root = _system.project_root()
    add("Install root", root is not None, str(root) if root else "set TRINAXAI_HOME or reinstall", critical=True)
    add("Service manager", _system.service_manager().is_file(), str(_system.service_manager()), critical=True)
    ollama_path = _find_ollama()
    ollama_api = _ollama_api_ok(_system.env_value("OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
    add(
        "Ollama command",
        bool(ollama_path or ollama_api),
        ollama_path or ("running API detected" if ollama_api else "install/start Ollama"),
        critical=True,
    )

    try:
        if root is None:
            raise FileNotFoundError("full TrinaxAI installation not found")
        status = run_process_group(
            [
                sys.executable,
                str(_system.service_manager()),
                "status",
                "--base-dir",
                str(root),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        service_items = json.loads(status.stdout or "[]") if status.returncode == 0 else []
        services_ok = bool(service_items) and all(bool(item.get("running")) for item in service_items)
        detail = (
            ", ".join(
                f"{item.get('display_name') or item.get('name')}={'running' if item.get('running') else 'stopped'}"
                for item in service_items
            )
            or (status.stderr or "no service status").strip()
        )
        add("Services", services_ok, detail[:220], critical=True)

        by_name = {str(item.get("name")): item for item in service_items}
        frontend = by_name.get("trinaxai-frontend", {})
        frontend_command = _process_command(frontend.get("pid"))
        actual_mode = _frontend_mode_from_command(frontend_command)
        expected_mode = (_system.load_dotenv_values().get("TRINAXAI_FRONTEND_MODE") or "preview").lower()
        if frontend.get("running"):
            mode_ok = actual_mode is None or actual_mode == expected_mode
            add(
                "Frontend mode",
                mode_ok,
                f"expected={expected_mode}, actual={actual_mode or 'unavailable'}",
                critical=True,
            )

        backend = by_name.get("rag_api", {})
        backend_command = _process_command(backend.get("pid"))
        safe_bind = _safe_backend_command(backend_command)
        if backend.get("running"):
            add(
                "Backend bind",
                safe_bind is not False,
                "loopback or enforced" if safe_bind is not False else "unsafe non-loopback listener",
                critical=True,
            )
    except Exception as exc:
        add("Services", False, str(exc), critical=True)

    try:
        health = client.health()
        indexed = bool(health.get("indexed"))
        projects = health.get("projects", []) or []
        collections = health.get("collections", []) or []
        add("RAG API", True, client.base_url, critical=True)
        add("Index built", indexed, "ready" if indexed else "run: trinaxai index .")
        add("Projects", True, str(len(projects)))
        add("Collections", True, ", ".join(c.get("id", "") for c in collections[:5]) or "none")
        try:
            stats = client.stats()
            add(
                "Usage stats",
                True,
                f"messages={stats.get('messages_total', 0)} tokens={stats.get('tokens_estimated', 0)}",
            )
        except Exception:
            pass
        try:
            mem = client.memory_summary()
            if mem.get("summary"):
                ui.panel(mem.get("summary", ""), title="Memory summary")
        except Exception:
            pass
    except Exception as exc:
        add("RAG API", False, f"{exc}; run: trinaxai start", critical=True)

    healthy = all(check["ok"] for check in checks if check["critical"])
    if bool(getattr(args, "json", False)):
        # Rich may hard-wrap long strings, which would corrupt JSON inside
        # quoted values. Machine output bypasses presentation formatting.
        sys.stdout.write(
            json.dumps({"healthy": healthy, "checks": checks}, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
    else:
        rows = [[check["check"], "OK" if check["ok"] else "FAIL", check["detail"]] for check in checks]
        ui.table(["check", "status", "detail"], rows, title="TrinaxAI doctor")
    if bool(getattr(args, "strict", False)):
        return 0 if healthy else 1
    # Human diagnostics remain non-fatal for compatibility; scripts should use
    # --strict (and usually --json) for a deterministic health gate.
    core_ok = all(
        check["ok"] for check in checks if check["check"] in {"Python package", "Install root", "Service manager"}
    )
    return 0 if core_ok else 1
