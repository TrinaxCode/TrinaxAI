"""
TrinaxAI — Cross-Platform Service Manager

Abstracts process lifecycle (start, stop, status) across Linux (systemd),
macOS (launchctl), and Windows (direct subprocess fallback).

The public API is deliberately minimal so callers (shell scripts, API endpoints)
don't need to know which platform backend is in use.
"""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


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
    "trinaxai-supervisor": ["trinaxai.service"],
}
SERVICE_DISPLAY_NAMES = {
    "ollama": "Ollama",
    "rag_api": "TrinaxAI RAG API",
    "trinaxai-frontend": "TrinaxAI PWA",
}


def service_display_name(name: str) -> str:
    """Stable UI label; platform unit/process names remain unchanged."""
    return SERVICE_DISPLAY_NAMES.get(name, name)


PRIVILEGED_LIFECYCLE_WRAPPER = Path("/usr/local/libexec/trinaxai/trinaxai-lifecycle")


def _systemd_units(name: str) -> list[str]:
    return SYSTEMD_SERVICE_ALIASES.get(name, [f"{name}.service"])


def _run_systemctl(args: list[str], *, check: bool = False, timeout: int = 30) -> subprocess.CompletedProcess:
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
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
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
                    return ProcessState(name=name, running=True, detail=f"started via systemd ({svc})")
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
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
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
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
                    pid = None
                    pid_result = _run_systemctl(
                        ["show", svc, "--property=MainPID", "--value"],
                        timeout=5,
                    )
                    try:
                        parsed_pid = int(pid_result.stdout.strip())
                        pid = parsed_pid if parsed_pid > 0 else None
                    except (TypeError, ValueError):
                        pass
                    return ProcessState(
                        name=name,
                        running=True,
                        pid=pid,
                        detail=f"active (systemd: {svc})",
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return _pgrep_status(name)


# ── macOS: launchctl + direct fallback ─────────────────────────────
_LAUNCHCTL = shutil.which("launchctl") or "/bin/launchctl"
LAUNCHCTL_LABELS = {"trinaxai-supervisor": "com.trinaxcode.trinaxai"}


def _launchctl_label(name: str) -> str:
    return LAUNCHCTL_LABELS.get(name, f"com.trinaxai.{name}")


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
        label = _launchctl_label(name)
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
        label = _launchctl_label(name)
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
        label = _launchctl_label(name)
        plist = Path.home() / f"Library/LaunchAgents/{label}.plist"
        if plist.exists():
            r = subprocess.run([_LAUNCHCTL, "list", label], timeout=5, capture_output=True, text=True)
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
                f"$_.CommandLine -like '*{pattern.replace(chr(39), chr(39) + chr(39))}*'" for pattern in patterns
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
                r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=5)
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
        return ProcessState(name=name, running=False, detail="pgrep/tasklist unavailable")


def _stop_by_name(name: str) -> ProcessState:
    """Gracefully terminate (SIGTERM) then force-kill (SIGKILL) if needed."""
    patterns = PROCESS_PATTERNS.get(name, [name])
    if sys.platform == "win32":
        escaped = " -or ".join(
            f"$_.CommandLine -like '*{pattern.replace(chr(39), chr(39) + chr(39))}*'" for pattern in patterns
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
        return ProcessState(name=name, running=False, detail="stopped matching processes")
    else:
        try:
            for pattern in patterns:
                subprocess.run(["pkill", "-TERM", "-f", pattern], timeout=10, capture_output=True)
            time.sleep(1)
            # Hard kill survivors
            for pattern in patterns:
                subprocess.run(["pkill", "-KILL", "-f", pattern], timeout=5, capture_output=True)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            if shutil.which("killall"):
                subprocess.run(["killall", name], timeout=10, capture_output=True)
        return ProcessState(name=name, running=False, detail="stopped matching processes")


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
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
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
            shell=False,
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


def _reap_zombie_children() -> None:
    """Reap any exited direct children so they don't linger as zombies.

    Services launched via ``_start_direct`` stay children of the long-running
    supervisor (``start_new_session`` detaches the session, not the parent).
    When a service dies and ``watch`` restarts it, the old PID would otherwise
    remain a zombie until this process exits. ``os.waitpid`` is unavailable on
    Windows, where the OS cleans up handles on its own, so it is skipped there.
    """
    if sys.platform == "win32" or not hasattr(os, "waitpid"):
        return
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        except OSError:
            return
        if pid == 0:
            return


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
# Stop in-process work and API/model owners before killing the browser gateway,
# so the HTTP response that initiated stop-all has time to leave the host.
FULL_SHUTDOWN_ORDER = [SUPERVISOR_SERVICE, "rag_api", "ollama", FRONTEND_SERVICE]
PROCESS_PATTERNS = {
    "ollama": ["ollama serve", "ollama"],
    "rag_api": ["uvicorn app.main:app", "uvicorn rag_api:app", "rag_api.py", "rag_api"],
    "trinaxai-frontend": [
        "node server.mjs",
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
    mode = env.get("TRINAXAI_FRONTEND_MODE", "serve").strip().lower()
    return "dev" if mode == "dev" else "serve"


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
    parsed = urlsplit(url)
    try:
        host_is_loopback = bool(parsed.hostname) and ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        host_is_loopback = parsed.hostname == "localhost"
    if parsed.scheme not in {"http", "https"} or not host_is_loopback:
        return False
    deadline = time.time() + timeout_seconds
    context = None
    if url.startswith("https://"):
        import ssl

        # Local development uses a generated self-signed certificate. The URL
        # was constrained above to HTTP(S) on loopback, so no remote identity is
        # trusted through this readiness probe.
        context = ssl._create_unverified_context()  # nosec B323
    while time.time() < deadline:
        try:
            # The URL scheme and loopback host were validated above.
            with urllib.request.urlopen(  # nosec B310
                url, timeout=2, context=context
            ) as response:
                if 200 <= int(response.status) < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.75)
    return False


def _rag_health_url(base_dir: str, env: dict[str, str]) -> str:
    scheme = "https" if _rag_uses_https(base_dir, env) else "http"
    port = env.get("TRINAXAI_PORT", "3333")
    return f"{scheme}://127.0.0.1:{port}/health"


def _rag_command(python: str, base_dir: str, env: dict[str, str]) -> list[str]:
    # The browser-facing gateway is the only LAN listener. Keeping FastAPI on
    # loopback makes the signed proxy identity an actual trust boundary.
    host = env.get("TRINAXAI_HOST", "127.0.0.1")
    allow_unsafe_bind = env.get("TRINAXAI_UNSAFE_BIND_BACKEND", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host.lower() == "localhost"
    if not is_loopback and not allow_unsafe_bind:
        host = "127.0.0.1"
    port = env.get("TRINAXAI_PORT", "3333")
    command = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
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

    if sys.platform == "win32" and mode == "dev":
        node = _known_windows_executable("node") or "node.exe"
        frontend_cmd = [
            node,
            os.path.abspath(os.path.join(base_dir, "chat-pwa", "node_modules", "vite", "bin", "vite.js")),
            mode,
            "--host",
            service_env.get("TRINAXAI_PWA_HOST", "127.0.0.1"),
            "--port",
            "3334",
        ]
    elif sys.platform == "win32":
        node = _known_windows_executable("node") or "node.exe"
        frontend_cmd = [node, os.path.abspath(os.path.join(base_dir, "chat-pwa", "server.mjs"))]
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


def _read_service_state(base_dir: str) -> dict:
    try:
        data = json.loads(_state_path(base_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _system_state(base_dir: str) -> str:
    return str(_read_service_state(base_dir).get("system_state") or "running")


def _ollama_owned(base_dir: str) -> bool:
    # Legacy installations have no ownership bit. Preserve their historical
    # behavior, while every newly observed external instance is recorded false.
    state = _read_service_state(base_dir)
    return bool(state.get("ollama_owned", True))


def _ollama_owned_for_stop_all(base_dir: str) -> bool:
    """Only stop Ollama when this installation explicitly owns it."""
    return _read_service_state(base_dir).get("ollama_owned") is True


def _write_service_state(base_dir: str, **changes: object) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_service_state(base_dir)
    data.update(changes)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_ai_enabled(base_dir: str, enabled: bool) -> None:
    _write_service_state(base_dir, ai_enabled=enabled)


def _try_privileged_wrapper(base_dir: str, action: str) -> list[ProcessState] | None:
    """Use the fixed, root-owned lifecycle wrapper for system installations."""
    if (
        platform.system() != "Linux"
        or os.getenv("TRINAXAI_PRIVILEGED_WRAPPER") == "1"
        or not hasattr(os, "geteuid")
        or os.geteuid() == 0
        or not shutil.which("sudo")
    ):
        return None

    if action not in {"stop-ai", "start-ai", "stop-all", "start-all", "reload-network"}:
        return None
    wrapper = PRIVILEGED_LIFECYCLE_WRAPPER
    if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
        return None

    try:
        result = subprocess.run(
            ["sudo", "-n", str(wrapper), action],
            timeout=90,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return [ProcessState(action, False, detail=f"privileged wrapper failed: {exc}")]

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "privileged wrapper failed").strip()
        return [ProcessState(action, False, detail=detail)]
    if action != "reload-network":
        enabled = action in {"start-ai", "start-all"}
        _write_service_state(
            base_dir,
            ai_enabled=enabled,
            system_state="running"
            if action == "start-all"
            else ("stopped_by_user" if action == "stop-all" else _system_state(base_dir)),
        )
    return [ProcessState(action, action != "stop-ai", detail=(result.stdout or "ok").strip())]


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


def _recovery_pid(base_dir: str) -> int | None:
    try:
        pid = int((Path(base_dir) / "storage" / "recovery.pid").read_text(encoding="ascii").strip())
        if pid <= 0:
            return None
        try:
            os.kill(pid, 0)
        except OSError:
            (Path(base_dir) / "storage" / "recovery.pid").unlink(missing_ok=True)
            return None
        return pid
    except (OSError, ValueError):
        return None


def _stop_recovery(base_dir: str) -> ProcessState:
    pid = _recovery_pid(base_dir)
    if not pid or pid == os.getpid():
        return ProcessState("recovery", False, detail="not running")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _recovery_pid(base_dir) == pid:
            time.sleep(0.1)
        return ProcessState("recovery", False, pid=pid, detail="stopped")
    except (OSError, subprocess.TimeoutExpired):
        return ProcessState("recovery", False, pid=pid, detail="already stopped")


def _start_recovery(base_dir: str) -> ProcessState:
    if _recovery_pid(base_dir):
        return ProcessState("recovery", True, pid=_recovery_pid(base_dir), detail="already running")
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    command = [sys.executable, os.path.join(base_dir, "recovery_server.py"), "--base-dir", base_dir]
    kwargs: dict[str, object] = {
        "cwd": base_dir,
        "stdin": subprocess.DEVNULL,
        "stdout": open(os.path.join(base_dir, "logs", "recovery.log"), "a", encoding="utf-8"),
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(command, **kwargs)
        return ProcessState("recovery", True, pid=proc.pid, detail="loopback recovery launch requested")
    except OSError as exc:
        return ProcessState("recovery", False, detail=f"recovery failed: {exc}")


def _start_supervisor(base_dir: str) -> None:
    command = [sys.executable, os.path.join(base_dir, "service_manager.py"), "watch", "--base-dir", base_dir]
    kwargs: dict[str, object] = {
        "cwd": base_dir,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _wait_port_free(host: str = "127.0.0.1", port: int | None = None, timeout: float = 10.0) -> bool:
    if port is None:
        try:
            port = int(_service_env(os.getcwd()).get("TRINAXAI_PWA_PORT", "3334"))
        except ValueError:
            port = 3334
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.2)
        try:
            if probe.connect_ex((host, port)) != 0:
                return True
        finally:
            probe.close()
        time.sleep(0.1)
    return False


def _wait_service_stopped(name: str, timeout: float = 5.0) -> bool:
    """Confirm a backend with a status API actually exited."""
    if not hasattr(_backend, "status"):
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if not _backend.status(name).running:
                return True
        except Exception:
            return False
        time.sleep(0.1)
    return False


def _recover_failed_start(base_dir: str, results: list[ProcessState]) -> list[ProcessState]:
    cleanup: list[ProcessState] = []
    for item in reversed(results):
        if item.name == "ollama" and not _ollama_owned_for_stop_all(base_dir):
            continue
        if "already running" in item.detail:
            continue
        cleanup.append(_backend.stop(item.name))
    if _wait_port_free():
        cleanup.append(_start_recovery(base_dir))
    else:
        cleanup.append(ProcessState("recovery", False, detail="gateway port remains occupied"))
    return cleanup


def _start_named(base_dir: str, name: str) -> ProcessState:
    current = _backend.status(name)
    if current.running:
        if name == "ollama" and "ollama_owned" not in _read_service_state(base_dir):
            _write_service_state(base_dir, ollama_owned=False)
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
    if name == "ollama" and state.running:
        _write_service_state(base_dir, ollama_owned=True)
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
    if name == FRONTEND_SERVICE and state.running:
        scheme = "https" if _rag_uses_https(base_dir, svc.get("env") or {}) else "http"
        url = f"{scheme}://127.0.0.1:{(svc.get('env') or {}).get('TRINAXAI_PWA_PORT', '3334')}/"
        if _wait_for_http(url, timeout_seconds=20):
            return ProcessState(name=name, running=True, pid=state.pid, detail=f"{state.detail}; health ok ({url})")
        return ProcessState(name=name, running=False, pid=state.pid, detail=f"frontend not ready: {url}")
    return state


def _stop_named(name: str) -> ProcessState:
    return _backend.stop(name)


def start_all(base_dir: str, lan_ip: str = "localhost") -> list[ProcessState]:
    """Start the full TrinaxAI stack in dependency order."""
    print("[lifecycle] startup requested")
    elevated = _try_privileged_wrapper(base_dir, "start-all")
    if elevated is not None:
        return elevated
    results: list[ProcessState] = []
    _write_service_state(base_dir, ai_enabled=True, system_state="starting")
    _set_ai_systemd_enabled(True)
    _stop_recovery(base_dir)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)

    for name in STARTUP_ORDER:
        state = _start_named(base_dir, name)
        results.append(state)
    healthy = all(item.running for item in results)
    if not healthy:
        results.extend(_recover_failed_start(base_dir, results))
        _write_service_state(base_dir, system_state="error")
        print("[lifecycle] startup failed")
        return results
    _write_service_state(base_dir, system_state="running")
    print("[lifecycle] system running")
    if os.getenv("TRINAXAI_START_SUPERVISOR") == "1":
        _start_supervisor(base_dir)
    return results


def start_frontend(base_dir: str) -> list[ProcessState]:
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    return [_start_named(base_dir, FRONTEND_SERVICE)]


def reload_network(base_dir: str) -> list[ProcessState]:
    """Restart certificate consumers after a LAN address change."""
    elevated = _try_privileged_wrapper(base_dir, "reload-network")
    if elevated is not None and elevated[-1].running:
        return elevated
    if platform.system() == "Linux" and shutil.which("systemctl"):
        result = _run_systemctl(["restart", "ai-rag.service", "trinaxai-frontend.service"], timeout=90)
        if result.returncode == 0:
            return [ProcessState("reload-network", True, detail="RAG and PWA restarted")]
        detail = (result.stderr or result.stdout or "systemctl restart failed").strip()
        return [ProcessState("reload-network", False, detail=detail)]
    stopped = stop_all()
    time.sleep(1)
    return [*stopped, *start_all(base_dir)]


def stop_ai(base_dir: str) -> list[ProcessState]:
    """Stop only the AI services and remember that AI should stay off on boot."""
    elevated = _try_privileged_wrapper(base_dir, "stop-ai")
    if elevated is not None:
        return elevated
    _write_service_state(base_dir, ai_enabled=False)
    _set_ai_systemd_enabled(False)
    results = [_stop_named(name) for name in AI_SHUTDOWN_ORDER if name != "ollama" or _ollama_owned(base_dir)]
    return results


def start_ai(base_dir: str) -> list[ProcessState]:
    """Enable AI autostart and start Ollama + RAG, leaving the PWA online."""
    elevated = _try_privileged_wrapper(base_dir, "start-ai")
    if elevated is not None:
        return elevated
    _write_service_state(base_dir, ai_enabled=True, system_state="starting")
    _set_ai_systemd_enabled(True)
    _stop_recovery(base_dir)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    results: list[ProcessState] = []
    for name in AI_SERVICES:
        results.append(_start_named(base_dir, name))
    results.extend(start_frontend(base_dir))
    _write_service_state(base_dir, system_state="running" if all(item.running for item in results) else "error")
    return results


def stop_all() -> list[ProcessState]:
    """Stop the full TrinaxAI stack in reverse dependency order."""
    results: list[ProcessState] = []
    for name in FULL_SHUTDOWN_ORDER:
        results.append(_backend.stop(name))
    return results


def stop_all_for_base(base_dir: str) -> list[ProcessState]:
    """Stop everything and keep AI disabled for the next boot."""
    print("[lifecycle] shutdown requested by local user")
    try:
        delay = min(2.0, max(0.0, float(os.getenv("TRINAXAI_STOP_ALL_DELAY", "0"))))
    except ValueError:
        delay = 0.0
    if delay:
        time.sleep(delay)
    _write_service_state(base_dir, ai_enabled=False, system_state="stopping")
    elevated = _try_privileged_wrapper(base_dir, "stop-all")
    _set_ai_systemd_enabled(False)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    results = list(elevated or [])
    if elevated is None:
        for name in FULL_SHUTDOWN_ORDER:
            if name == "ollama" and not _ollama_owned_for_stop_all(base_dir):
                continue
            results.append(_backend.stop(name))
    else:
        # The wrapper owns root system units; this user-level unit still needs
        # to be stopped separately so it cannot rebuild the stack.
        results.append(_backend.stop(SUPERVISOR_SERVICE))
    service_names = [name for name in FULL_SHUTDOWN_ORDER if name != "ollama" or _ollama_owned_for_stop_all(base_dir)]
    remaining = [name for name in service_names if not _wait_service_stopped(name)]
    if remaining or not _wait_port_free():
        results.append(ProcessState("recovery", False, detail="port 3334 is still occupied"))
        _write_service_state(base_dir, system_state="error")
        return results
    _write_service_state(base_dir, system_state="stopped_by_user")
    results.append(_start_recovery(base_dir))
    print("[lifecycle] recovery server requested on loopback")
    return results


def _quote_cmd_arg(value: str) -> str:
    return '"' + value.replace('"', r"\"") + '"'


def _systemd_quote(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _systemd_path(value: str | Path) -> str:
    """Escape a path for systemd directives that do not use shell-style quotes."""
    return str(value).replace("\\", "\\\\").replace(" ", "\\x20")


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
            f"WorkingDirectory={_systemd_path(base_dir)}\n"
            f"ExecStart={_systemd_quote(python)} {_systemd_quote(Path(base_dir) / 'service_manager.py')} watch --base-dir {_systemd_quote(base_dir)}\n"
            "Restart=on-failure\n"
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
            detail = (enable_result.stderr or reload_result.stderr or "systemctl --user failed").strip()
            return ProcessState("autostart", False, detail=detail)
        return ProcessState("autostart", True, detail=f"enabled user systemd: {service_file}")
    if system == "Darwin":
        label = "com.trinaxcode.trinaxai"
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / f"{label}.plist"
        payload = {
            "Label": label,
            "ProgramArguments": [
                python,
                str(Path(base_dir) / "service_manager.py"),
                "watch",
                "--base-dir",
                base_dir,
            ],
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "WorkingDirectory": base_dir,
            "StandardOutPath": str(Path(base_dir) / "logs" / "supervisor.log"),
            "StandardErrorPath": str(Path(base_dir) / "logs" / "supervisor.err.log"),
        }
        with plist.open("wb") as handle:
            plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=False)
        subprocess.run(["launchctl", "unload", str(plist)], timeout=10, capture_output=True)
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
        plist = Path.home() / "Library" / "LaunchAgents" / "com.trinaxcode.trinaxai.plist"
        if plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], timeout=10, capture_output=True)
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
        _reap_zombie_children()
        if _system_state(base_dir) == "stopped_by_user":
            if not _recovery_pid(base_dir):
                recovery = _start_recovery(base_dir)
                print(f"recovery: {recovery.detail}")
            time.sleep(max(5, interval))
            return
        wanted = [FRONTEND_SERVICE]
        if _read_ai_enabled(base_dir):
            wanted = STARTUP_ORDER
        for name in wanted:
            state = _backend.status(name)
            if state.running:
                continue
            restarted = _start_named(base_dir, name)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] restarted {name}: {restarted.detail}")
            if name == "ollama":
                continue
        time.sleep(max(5, interval))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TrinaxAI cross-platform service manager")
    parser.add_argument(
        "action",
        choices=[
            "start",
            "start-ai",
            "start-frontend",
            "start-all",
            "reload-network",
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
    parser.add_argument("--json", action="store_true", help="Emit machine-readable status output")
    args = parser.parse_args(argv)

    if args.action in {"start", "start-all"}:
        items = start_all(args.base_dir)
        for item in items:
            print(f"{item.name}: {item.detail}")
        return 0 if all(item.running for item in items) else 1
    elif args.action == "start-ai":
        items = start_ai(args.base_dir)
        for item in items:
            print(f"{item.name}: {item.detail}")
        return 0 if all(item.running for item in items) else 1
    elif args.action == "start-frontend":
        items = start_frontend(args.base_dir)
        for item in items:
            print(f"{item.name}: {item.detail}")
        return 0 if all(item.running for item in items) else 1
    elif args.action == "reload-network":
        items = reload_network(args.base_dir)
        for item in items:
            print(f"{item.name}: {item.detail}")
        return 0 if all(item.running for item in items[-len(STARTUP_ORDER) :]) else 1
    elif args.action == "stop" or args.action == "stop-ai":
        for item in stop_ai(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "stop-all":
        for item in stop_all_for_base(args.base_dir):
            print(f"{item.name}: {item.detail}")
    elif args.action == "status":
        items = status_all()
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "name": item.name,
                            "display_name": service_display_name(item.name),
                            "running": item.running,
                            "pid": item.pid,
                            "detail": item.detail,
                        }
                        for item in items
                    ],
                    separators=(",", ":"),
                )
            )
        else:
            for item in items:
                print(f"{service_display_name(item.name)}: {'running' if item.running else 'stopped'} {item.detail}")
    elif args.action == "watch":
        watch(args.base_dir, args.interval)
    elif args.action == "enable-autostart":
        item = enable_autostart(args.base_dir)
        print(f"{item.name}: {item.detail}")
        return 0 if item.running else 1
    elif args.action == "disable-autostart":
        item = disable_autostart(args.base_dir)
        print(f"{item.name}: {item.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
