"""
TrinaxAI — Cross-Platform Service Manager

Abstracts process lifecycle (start, stop, status) across Linux (systemd),
macOS (launchctl), and Windows (direct subprocess fallback).

The public API is deliberately minimal so callers (shell scripts, API endpoints)
don't need to know which platform backend is in use.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


# ── Public data types ──────────────────────────────────────────────
@dataclass
class ProcessState:
    """Result of a status / is-running check."""

    name: str
    running: bool
    pid: int | None = None
    detail: str = ""


# ── Backend interface ──────────────────────────────────────────────
class _Backend:
    """Pluggable backend. Each platform implements this."""

    def start(
        self,
        name: str,
        *,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        log_file: str | None = None,
    ) -> ProcessState:
        raise NotImplementedError

    def stop(self, name: str) -> ProcessState:
        raise NotImplementedError

    def status(self, name: str) -> ProcessState:
        raise NotImplementedError


def _windows_no_window_kwargs() -> dict[str, object]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


# ── Linux: systemd with direct fallback ────────────────────────────
_SYSTEMCTL = shutil.which("systemctl") or "/usr/bin/systemctl"
SYSTEMD_SERVICE_ALIASES = {
    "ollama": ["ollama.service"],
    "rag_api": ["rag_api.service", "ai-rag.service"],
    "trinaxai-frontend": ["trinaxai-frontend.service"],
}


def _systemd_units(name: str) -> list[str]:
    return SYSTEMD_SERVICE_ALIASES.get(name, [f"{name}.service"])


def _run_systemctl(
    args: list[str], *, check: bool = False, timeout: int = 30
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [_SYSTEMCTL, *args],
        check=False,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and shutil.which("sudo"):
        sudo_result = subprocess.run(
            ["sudo", "-n", _SYSTEMCTL, *args],
            check=False,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        if sudo_result.returncode == 0:
            result = sudo_result
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, output=result.stdout, stderr=result.stderr
        )
    return result


class _SystemdBackend(_Backend):
    def start(
        self,
        name: str,
        *,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        log_file: str | None = None,
    ) -> ProcessState:
        try:
            for svc in _systemd_units(name):
                result = _run_systemctl(["start", svc], timeout=30)
                if result.returncode == 0:
                    return ProcessState(
                        name=name, running=True, detail=f"started via systemd ({svc})"
                    )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to direct subprocess
            pass
        return _start_direct(name, command=command, cwd=cwd, env=env, log_file=log_file)

    def stop(self, name: str) -> ProcessState:
        stopped: list[str] = []
        try:
            for svc in _systemd_units(name):
                result = _run_systemctl(["stop", svc], timeout=30)
                if result.returncode == 0:
                    stopped.append(svc)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        fallback = _stop_by_name(name)
        if stopped:
            detail = "stopped via systemd: " + ", ".join(stopped)
            if fallback.detail:
                detail += f"; {fallback.detail}"
            return ProcessState(name=name, running=False, detail=detail)
        return fallback

    def status(self, name: str) -> ProcessState:
        # Try systemd first
        try:
            for svc in _systemd_units(name):
                r = _run_systemctl(["is-active", "--quiet", svc], timeout=5)
                if r.returncode == 0:
                    return ProcessState(
                        name=name, running=True, detail=f"active (systemd: {svc})"
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return _pgrep_status(name)


# ── macOS: launchctl + direct fallback ─────────────────────────────
_LAUNCHCTL = shutil.which("launchctl") or "/bin/launchctl"


class _LaunchctlBackend(_Backend):
    def start(
        self,
        name: str,
        *,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        log_file: str | None = None,
    ) -> ProcessState:
        label = f"com.trinaxai.{name}"
        plist = Path.home() / f"Library/LaunchAgents/{label}.plist"
        if plist.exists():
            try:
                subprocess.run(
                    [_LAUNCHCTL, "load", str(plist)],
                    check=True,
                    timeout=10,
                    capture_output=True,
                    text=True,
                )
                return ProcessState(name=name, running=True, detail=f"loaded {label}")
            except subprocess.CalledProcessError:
                pass
        # Fall back to direct subprocess
        return _start_direct(name, command=command, cwd=cwd, env=env, log_file=log_file)

    def stop(self, name: str) -> ProcessState:
        label = f"com.trinaxai.{name}"
        plist = Path.home() / f"Library/LaunchAgents/{label}.plist"
        if plist.exists():
            subprocess.run(
                [_LAUNCHCTL, "unload", str(plist)],
                timeout=10,
                capture_output=True,
                text=True,
            )
        return _stop_by_name(name)

    def status(self, name: str) -> ProcessState:
        label = f"com.trinaxai.{name}"
        plist = Path.home() / f"Library/LaunchAgents/{label}.plist"
        if plist.exists():
            r = subprocess.run(
                [_LAUNCHCTL, "list", label], timeout=5, capture_output=True, text=True
            )
            if r.returncode == 0:
                return ProcessState(name=name, running=True, detail=f"loaded {label}")
        return _pgrep_status(name)


# ── Windows / generic: subprocess only ─────────────────────────────
class _DirectBackend(_Backend):
    def start(
        self,
        name: str,
        *,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        log_file: str | None = None,
    ) -> ProcessState:
        return _start_direct(name, command=command, cwd=cwd, env=env, log_file=log_file)

    def stop(self, name: str) -> ProcessState:
        return _stop_by_name(name)

    def status(self, name: str) -> ProcessState:
        return _pgrep_status(name)


# ── Shared helpers ─────────────────────────────────────────────────
def _pgrep_status(name: str) -> ProcessState:
    """Check if a process with *name* in its command line is running."""
    try:
        if sys.platform == "win32":
            patterns = PROCESS_PATTERNS.get(name, [name])
            escaped = " -or ".join(
                f"$_.CommandLine -like '*{pattern.replace(chr(39), chr(39) + chr(39))}*'"
                for pattern in patterns
            )
            script = (
                "Get-CimInstance Win32_Process | "
                f"Where-Object {{ $_.ProcessId -ne $PID -and $_.CommandLine -and ({escaped}) }} | "
                "Select-Object -First 1 -ExpandProperty ProcessId"
            )
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                timeout=8,
                **_windows_no_window_kwargs(),
            )
            running = bool(r.stdout.strip())
            pid = int(r.stdout.strip().splitlines()[0]) if running else None
            return ProcessState(
                name=name,
                running=running,
                pid=pid,
                detail=f"pid {pid} (windows)" if running else "not found",
            )
        else:
            for pattern in PROCESS_PATTERNS.get(name, [name]):
                r = subprocess.run(
                    ["pgrep", "-f", pattern], capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0 and r.stdout.strip():
                    pid = int(r.stdout.strip().split("\n")[0])
                    return ProcessState(
                        name=name,
                        running=True,
                        pid=pid,
                        detail=f"pid {pid} ({pattern})",
                    )
            return ProcessState(name=name, running=False, detail="not found")
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return ProcessState(
            name=name, running=False, detail="pgrep/tasklist unavailable"
        )


def _stop_by_name(name: str) -> ProcessState:
    """Gracefully terminate (SIGTERM) then force-kill (SIGKILL) if needed."""
    patterns = PROCESS_PATTERNS.get(name, [name])
    if sys.platform == "win32":
        escaped = " -or ".join(
            f"$_.CommandLine -like '*{pattern.replace(chr(39), chr(39) + chr(39))}*'"
            for pattern in patterns
        )
        script = (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.ProcessId -ne $PID -and $_.CommandLine -and ({escaped}) }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            timeout=15,
            **_windows_no_window_kwargs(),
        )
        return ProcessState(
            name=name, running=False, detail="stopped matching processes"
        )
    else:
        try:
            for pattern in patterns:
                subprocess.run(
                    ["pkill", "-TERM", "-f", pattern], timeout=10, capture_output=True
                )
            time.sleep(1)
            # Hard kill survivors
            for pattern in patterns:
                subprocess.run(
                    ["pkill", "-KILL", "-f", pattern], timeout=5, capture_output=True
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            if shutil.which("killall"):
                subprocess.run(["killall", name], timeout=10, capture_output=True)
            pass
        return ProcessState(
            name=name, running=False, detail="stopped matching processes"
        )


def _start_direct(
    name: str,
    *,
    command: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    log_file: str | None = None,
) -> ProcessState:
    """Start a process directly, detaching it from the parent."""
    merged_env = {**os.environ, **(env or {})}
    log_fh = open(log_file, "a", encoding="utf-8") if log_file else subprocess.DEVNULL
    popen_kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        ) | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        popen_kwargs["startupinfo"] = startupinfo
    else:
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=merged_env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        return ProcessState(
            name=name,
            running=True,
            pid=proc.pid or 0,
            detail=f"started directly (pid {proc.pid})",
        )
    except Exception as exc:
        return ProcessState(name=name, running=False, detail=f"failed: {exc}")
    finally:
        if log_file and hasattr(log_fh, "close"):
            log_fh.close()


# ── Backend selection ──────────────────────────────────────────────
def _detect_backend() -> _Backend:
    system = platform.system()
    if system == "Linux":
        # Check if systemd is actually available (e.g., Docker containers may not have it).
        if shutil.which("systemctl"):
            return _SystemdBackend()
        return _DirectBackend()
    if system == "Darwin":
        return _LaunchctlBackend()
    # Windows or unknown → direct subprocess management.
    return _DirectBackend()


_backend: _Backend = _detect_backend()

# ── Public API ─────────────────────────────────────────────────────
STARTUP_ORDER = ["ollama", "rag_api", "trinaxai-frontend"]
# Stop RAG last: /system/shutdown can be launched from the RAG service itself,
# and killing that cgroup first can terminate this manager before Ollama stops.
SHUTDOWN_ORDER = ["trinaxai-frontend", "ollama", "rag_api"]
AI_SERVICES = ["ollama", "rag_api"]
AI_SHUTDOWN_ORDER = ["ollama", "rag_api"]
FRONTEND_SERVICE = "trinaxai-frontend"
SUPERVISOR_SERVICE = "trinaxai-supervisor"
FULL_SHUTDOWN_ORDER = [SUPERVISOR_SERVICE, *SHUTDOWN_ORDER]
PROCESS_PATTERNS = {
    "ollama": ["ollama serve", "ollama"],
    "rag_api": ["uvicorn rag_api:app", "rag_api.py", "rag_api"],
    "trinaxai-frontend": [
        "vite --host",
        "vite preview",
        "vite.js preview",
        "node_modules\\vite\\bin\\vite.js",
        "node_modules/vite/bin/vite.js",
        "npm run dev",
        "npm run preview",
        "trinaxai-frontend",
    ],
    "trinaxai-supervisor": [
        'service_manager.py" watch',
        "service_manager.py watch",
        "service_manager.py' watch",
    ],
}


def _windows_hidden_python(python: str) -> str:
    if sys.platform != "win32":
        return python
    path = Path(python)
    if path.name.lower() != "python.exe":
        return python
    pythonw = path.with_name("pythonw.exe")
    return str(pythonw) if pythonw.exists() else python


def _known_windows_executable(name: str) -> str | None:
    if sys.platform != "win32":
        return shutil.which(name)
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    candidates = {
        "ollama": [
            Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe",
            Path(program_files) / "Ollama" / "ollama.exe",
        ],
        "node": [
            Path(program_files) / "nodejs" / "node.exe",
        ],
    }.get(name.lower(), [])
    found = shutil.which(name) or shutil.which(f"{name}.exe")
    if found:
        return found
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _read_env_file(base_dir: str) -> dict[str, str]:
    env_path = Path(base_dir) / ".env"
    values: dict[str, str] = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _service_env(base_dir: str) -> dict[str, str]:
    file_env = _read_env_file(base_dir)
    return {**file_env, **os.environ}


def _frontend_script(env: dict[str, str]) -> str:
    mode = env.get("TRINAXAI_FRONTEND_MODE", "preview").strip().lower()
    return "dev" if mode == "dev" else "preview"


def _rag_https_files(base_dir: str) -> tuple[str, str] | None:
    cert_dir = Path(base_dir) / "chat-pwa" / "certs"
    key_file = cert_dir / "localhost-key.pem"
    cert_file = cert_dir / "localhost.pem"
    if key_file.is_file() and cert_file.is_file():
        return str(key_file), str(cert_file)
    return None


def _rag_uses_https(base_dir: str, env: dict[str, str]) -> bool:
    requested = env.get("TRINAXAI_RAG_HTTPS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    return requested and _rag_https_files(base_dir) is not None


def _wait_for_http(url: str, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    context = None
    if url.startswith("https://"):
        import ssl

        context = ssl._create_unverified_context()
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2, context=context) as response:
                if 200 <= int(response.status) < 500:
                    return True
        except Exception:
            time.sleep(0.75)
    return False


def _rag_health_url(base_dir: str, env: dict[str, str]) -> str:
    scheme = "https" if _rag_uses_https(base_dir, env) else "http"
    port = env.get("TRINAXAI_PORT", "3333")
    return f"{scheme}://127.0.0.1:{port}/health"


def _rag_command(python: str, base_dir: str, env: dict[str, str]) -> list[str]:
    host = env.get("TRINAXAI_HOST", "0.0.0.0")
    port = env.get("TRINAXAI_PORT", "3333")
    command = [
        python,
        "-m",
        "uvicorn",
        "rag_api:app",
        "--host",
        host,
        "--port",
        port,
    ]
    ssl_files = _rag_https_files(base_dir) if _rag_uses_https(base_dir, env) else None
    if ssl_files:
        key_file, cert_file = ssl_files
        command.extend(["--ssl-keyfile", key_file, "--ssl-certfile", cert_file])
    return command


def _service_specs(base_dir: str) -> dict[str, dict]:
    service_env = _service_env(base_dir)
    python = _windows_hidden_python(service_env.get("TRINAXAI_PYTHON", sys.executable))
    npm = shutil.which("npm") or "npm"
    mode = _frontend_script(service_env)

    if sys.platform == "win32":
        node = _known_windows_executable("node") or "node.exe"
        frontend_cmd = [
            node,
            os.path.abspath(
                os.path.join(
                    base_dir, "chat-pwa", "node_modules", "vite", "bin", "vite.js"
                )
            ),
            mode,
            "--host",
            "0.0.0.0",
            "--port",
            "3334",
        ]
    else:
        frontend_cmd = [npm, "run", mode]

    return {
        "ollama": {
            "command": [_known_windows_executable("ollama") or "ollama", "serve"],
            "env": service_env,
            "log_file": os.path.join(base_dir, "logs", "ollama.log"),
        },
        "rag_api": {
            "command": _rag_command(python, base_dir, service_env),
            "cwd": base_dir,
            "env": service_env,
            "log_file": os.path.join(base_dir, "logs", "rag_api.log"),
        },
        "trinaxai-frontend": {
            "command": frontend_cmd,
            "cwd": os.path.join(base_dir, "chat-pwa"),
            "env": service_env,
            "log_file": os.path.join(base_dir, "logs", "frontend.log"),
        },
    }


def _state_path(base_dir: str) -> Path:
    return Path(base_dir) / "storage" / "service_state.json"


def _read_ai_enabled(base_dir: str) -> bool:
    path = _state_path(base_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("ai_enabled", True))
    except Exception:
        return True


def _write_ai_enabled(base_dir: str, enabled: bool) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"ai_enabled": enabled}, indent=2), encoding="utf-8")
    tmp.replace(path)


def _try_privileged_wrapper(base_dir: str, action: str) -> list[ProcessState] | None:
    """Use legacy sudoers wrappers for system-level installs when available."""
    if (
        platform.system() != "Linux"
        or os.getenv("TRINAXAI_PRIVILEGED_WRAPPER") == "1"
        or not hasattr(os, "geteuid")
        or os.geteuid() == 0
        or not shutil.which("sudo")
    ):
        return None

    if action not in {"stop-ai", "start-ai"}:
        return None
    script_name = "shutdown_ai.sh" if action == "stop-ai" else "startup_ai.sh"
    script = Path(base_dir) / script_name
    if not script.exists() or not os.access(script, os.X_OK):
        return None

    try:
        result = subprocess.run(
            ["sudo", "-n", str(script)],
            timeout=90,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return [ProcessState(action, False, detail=f"privileged wrapper failed: {exc}")]

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "privileged wrapper failed").strip()
        return [ProcessState(action, False, detail=detail)]
    return [
        ProcessState(
            action, action != "stop-ai", detail=(result.stdout or "ok").strip()
        )
    ]


def _systemd_set_enabled(name: str, enabled: bool, *, stop_now: bool = False) -> str:
    """Best-effort toggle for persistent systemd units on Linux.

    This keeps legacy systemd deployments aligned with the persisted AI state:
    when AI is turned off, the units should not come back on the next boot;
    when AI is turned on, the units should be enabled again.
    """
    if platform.system() != "Linux" or not shutil.which("systemctl"):
        return ""

    action = "enable" if enabled else "disable"
    details: list[str] = []
    for svc in _systemd_units(name):
        args = [action, svc] if enabled or not stop_now else [action, "--now", svc]
        try:
            result = _run_systemctl(args, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            details.append(f"{action} {svc} skipped: {exc}")
            continue

        if result.returncode == 0:
            details.append(f"{action}d {svc}")
            continue

        detail = (result.stderr or result.stdout or "").strip()
        details.append(f"{action} {svc} failed{': ' + detail if detail else ''}")
    return "; ".join(details)


def _set_ai_systemd_enabled(enabled: bool, *, stop_now: bool = False) -> list[str]:
    details: list[str] = []
    for name in AI_SERVICES:
        detail = _systemd_set_enabled(name, enabled, stop_now=stop_now)
        if detail:
            details.append(detail)
    return details


def _start_named(base_dir: str, name: str) -> ProcessState:
    current = _backend.status(name)
    if current.running:
        return ProcessState(
            name=name,
            running=True,
            pid=current.pid,
            detail=f"already running ({current.detail})",
        )
    services = _service_specs(base_dir)
    svc = services[name]
    state = _backend.start(
        name,
        command=svc["command"],
        cwd=svc.get("cwd"),
        env=svc.get("env"),
        log_file=svc.get("log_file"),
    )
    if name == "rag_api" and state.running:
        url = _rag_health_url(base_dir, svc.get("env") or {})
        if _wait_for_http(url, timeout_seconds=20):
            return ProcessState(
                name=name,
                running=True,
                pid=state.pid,
                detail=f"{state.detail}; health ok ({url})",
            )
        current = _backend.status(name)
        if not current.running:
            return ProcessState(
                name=name,
                running=False,
                detail=f"started but exited before health check. See logs/rag_api.log ({url})",
            )
        return ProcessState(
            name=name,
            running=True,
            pid=current.pid or state.pid,
            detail=f"{state.detail}; health not ready yet. See logs/rag_api.log ({url})",
        )
    return state


def _stop_named(name: str) -> ProcessState:
    return _backend.stop(name)


def start_all(base_dir: str, lan_ip: str = "localhost") -> list[ProcessState]:
    """Start the full TrinaxAI stack in dependency order."""
    elevated = _try_privileged_wrapper(base_dir, "start-ai")
    if elevated is not None:
        return elevated
    results: list[ProcessState] = []
    _write_ai_enabled(base_dir, True)
    _set_ai_systemd_enabled(True)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)

    for name in STARTUP_ORDER:
        state = _start_named(base_dir, name)
        results.append(state)
        if name == "ollama":
            # Give Ollama a moment to bind its port.
            time.sleep(2)
    return results


def start_frontend(base_dir: str) -> list[ProcessState]:
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    return [_start_named(base_dir, FRONTEND_SERVICE)]


def stop_ai(base_dir: str) -> list[ProcessState]:
    """Stop only the AI services and remember that AI should stay off on boot."""
    elevated = _try_privileged_wrapper(base_dir, "stop-ai")
    if elevated is not None:
        return elevated
    _write_ai_enabled(base_dir, False)
    _set_ai_systemd_enabled(False)
    results = [_stop_named(name) for name in AI_SHUTDOWN_ORDER]
    return results


def start_ai(base_dir: str) -> list[ProcessState]:
    """Enable AI autostart and start Ollama + RAG, leaving the PWA online."""
    elevated = _try_privileged_wrapper(base_dir, "start-ai")
    if elevated is not None:
        return elevated
    _write_ai_enabled(base_dir, True)
    _set_ai_systemd_enabled(True)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    results: list[ProcessState] = []
    for name in AI_SERVICES:
        results.append(_start_named(base_dir, name))
        if name == "ollama":
            time.sleep(2)
    results.extend(start_frontend(base_dir))
    return results


def stop_all() -> list[ProcessState]:
    """Stop the full TrinaxAI stack in reverse dependency order."""
    results: list[ProcessState] = []
    for name in FULL_SHUTDOWN_ORDER:
        results.append(_backend.stop(name))
    return results


def stop_all_for_base(base_dir: str) -> list[ProcessState]:
    """Stop everything and keep AI disabled for the next boot."""
    _write_ai_enabled(base_dir, False)
    _set_ai_systemd_enabled(False)
    return stop_all()


def _quote_cmd_arg(value: str) -> str:
    return '"' + value.replace('"', r"\"") + '"'


def _systemd_quote(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def enable_autostart(base_dir: str) -> ProcessState:
    """Install an OS autostart supervisor.

    The supervisor always keeps the PWA available. AI services start only when
    storage/service_state.json says ai_enabled=true.
    """
    python = sys.executable
    system = platform.system()
    if system == "Linux" and shutil.which("systemctl"):
        service_dir = Path.home() / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / "trinaxai.service"
        service_file.write_text(
            "[Unit]\n"
            "Description=TrinaxAI local supervisor\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"WorkingDirectory={_systemd_quote(base_dir)}\n"
            f"ExecStart={_systemd_quote(python)} {_systemd_quote(Path(base_dir) / 'service_manager.py')} watch --base-dir {_systemd_quote(base_dir)}\n"
            "Restart=always\n"
            "RestartSec=10\n\n"
            "[Install]\n"
            "WantedBy=default.target\n",
            encoding="utf-8",
        )
        reload_result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            timeout=20,
            capture_output=True,
            text=True,
        )
        enable_result = subprocess.run(
            ["systemctl", "--user", "enable", "--now", "trinaxai.service"],
            timeout=30,
            capture_output=True,
            text=True,
        )
        if reload_result.returncode != 0 or enable_result.returncode != 0:
            detail = (
                enable_result.stderr
                or reload_result.stderr
                or "systemctl --user failed"
            ).strip()
            return ProcessState("autostart", False, detail=detail)
        return ProcessState(
            "autostart", True, detail=f"enabled user systemd: {service_file}"
        )
    if system == "Darwin":
        label = "com.trinaxcode.trinaxai"
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / f"{label}.plist"
        plist.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            "<dict>\n"
            "  <key>Label</key><string>com.trinaxcode.trinaxai</string>\n"
            "  <key>ProgramArguments</key>\n"
            "  <array>\n"
            f"    <string>{python}</string>\n"
            f"    <string>{Path(base_dir) / 'service_manager.py'}</string>\n"
            "    <string>watch</string>\n"
            "    <string>--base-dir</string>\n"
            f"    <string>{base_dir}</string>\n"
            "  </array>\n"
            "  <key>RunAtLoad</key><true/>\n"
            "  <key>KeepAlive</key><true/>\n"
            f"  <key>WorkingDirectory</key><string>{base_dir}</string>\n"
            f"  <key>StandardOutPath</key><string>{Path(base_dir) / 'logs' / 'supervisor.log'}</string>\n"
            f"  <key>StandardErrorPath</key><string>{Path(base_dir) / 'logs' / 'supervisor.err.log'}</string>\n"
            "</dict>\n"
            "</plist>\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["launchctl", "unload", str(plist)], timeout=10, capture_output=True
        )
        load_result = subprocess.run(
            ["launchctl", "load", str(plist)],
            timeout=10,
            capture_output=True,
            text=True,
        )
        if load_result.returncode != 0:
            return ProcessState(
                "autostart",
                False,
                detail=(load_result.stderr or "launchctl load failed").strip(),
            )
        return ProcessState("autostart", True, detail=f"enabled launch agent: {plist}")
    if system == "Windows":
        python = _windows_hidden_python(python)
        startup = (
            Path(os.environ.get("APPDATA", str(Path.home())))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        startup.mkdir(parents=True, exist_ok=True)
        old_cmd = startup / "TrinaxAI.cmd"
        old_cmd.unlink(missing_ok=True)
        vbs = startup / "TrinaxAI.vbs"
        command = (
            f"{_quote_cmd_arg(python)} "
            f"{_quote_cmd_arg(str(Path(base_dir) / 'service_manager.py'))} "
            f"watch --base-dir {_quote_cmd_arg(base_dir)}"
        )
        vbs.write_text(
            'Set shell = CreateObject("WScript.Shell")\r\n'
            f'shell.CurrentDirectory = "{str(base_dir).replace(chr(34), chr(34) + chr(34))}"\r\n'
            f'shell.Run "{command.replace(chr(34), chr(34) + chr(34))}", 0, False\r\n',
            encoding="utf-8",
        )
        return ProcessState("autostart", True, detail=f"enabled Windows Startup: {vbs}")
    return ProcessState("autostart", False, detail="autostart backend unavailable")


def disable_autostart(base_dir: str) -> ProcessState:
    system = platform.system()
    if system == "Linux" and shutil.which("systemctl"):
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "trinaxai.service"],
            timeout=30,
            capture_output=True,
        )
        return ProcessState("autostart", False, detail="disabled user systemd")
    if system == "Darwin":
        plist = (
            Path.home() / "Library" / "LaunchAgents" / "com.trinaxcode.trinaxai.plist"
        )
        if plist.exists():
            subprocess.run(
                ["launchctl", "unload", str(plist)], timeout=10, capture_output=True
            )
            plist.unlink(missing_ok=True)
        return ProcessState("autostart", False, detail="disabled launch agent")
    if system == "Windows":
        startup = (
            Path(os.environ.get("APPDATA", str(Path.home())))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        for name in ("TrinaxAI.cmd", "TrinaxAI.vbs"):
            (startup / name).unlink(missing_ok=True)
        return ProcessState("autostart", False, detail="disabled Windows Startup")
    return ProcessState("autostart", False, detail="autostart backend unavailable")


def status_all() -> list[ProcessState]:
    return [_backend.status(name) for name in SHUTDOWN_ORDER]


def status(name: str) -> ProcessState:
    return _backend.status(name)


def watch(base_dir: str, interval: int = 15) -> None:
    """Keep the local stack alive on platforms without a real service manager.

    Linux systemd services already use Restart=on-failure. This loop is the
    cross-platform fallback for macOS, Windows, WSL, and direct subprocess runs.
    """
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    print(f"TrinaxAI supervisor watching services every {interval}s")
    while True:
        wanted = [FRONTEND_SERVICE]
        if _read_ai_enabled(base_dir):
            wanted = STARTUP_ORDER
        for name in wanted:
            state = _backend.status(name)
            if state.running:
                continue
            restarted = _start_named(base_dir, name)
            print(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] restarted {name}: {restarted.detail}"
            )
            if name == "ollama":
                time.sleep(2)
        time.sleep(max(5, interval))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="TrinaxAI cross-platform service manager"
    )
    parser.add_argument(
        "action",
        choices=[
            "start",
            "start-ai",
            "start-frontend",
            "stop",
            "stop-ai",
            "stop-all",
            "status",
            "watch",
            "enable-autostart",
            "disable-autostart",
        ],
    )
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    if args.action == "start":
        for item in start_all(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "start-ai":
        for item in start_ai(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "start-frontend":
        for item in start_frontend(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "stop":
        for item in stop_ai(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "stop-ai":
        for item in stop_ai(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "stop-all":
        for item in stop_all_for_base(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "status":
        for item in status_all():
            print(
                f"{item.name}: {'running' if item.running else 'stopped'} {item.detail}"
            )
    elif args.action == "watch":
        watch(args.base_dir, args.interval)
    elif args.action == "enable-autostart":
        item = enable_autostart(args.base_dir)
        print(f"{item.name}: {item.detail}")
        sys.exit(0 if item.running else 1)
    elif args.action == "disable-autostart":
        item = disable_autostart(args.base_dir)
        print(f"{item.name}: {item.detail}")
