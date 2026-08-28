from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import service_manager as sm


def _completed(returncode=0, *, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr, args=[])


def test_service_manager_low_level_platform_and_wait_edges(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(1))
    assert sm._pgrep_status("missing").running is False

    calls = []
    responses = iter([FileNotFoundError("pkill"), _completed()])

    def stop_run(command, **kwargs):
        calls.append(command)
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(sm.subprocess, "run", stop_run)
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/killall" if name == "killall" else None)
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._stop_by_name("custom").running is False
    assert calls[-1] == ["killall", "custom"]

    monkeypatch.setattr(sm.sys, "platform", "win32")
    monkeypatch.setattr(sm.shutil, "which", lambda name: "C:/Ollama/ollama.exe" if name == "ollama.exe" else None)
    assert sm._known_windows_executable("ollama") == "C:/Ollama/ollama.exe"

    env_file = tmp_path / ".env"
    env_file.write_text("=ignored\nTRINAXAI_PORT=3334\n", encoding="utf-8")
    assert sm._read_env_file(str(tmp_path))["TRINAXAI_PORT"] == "3334"

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(sm.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._wait_for_http("https://127.0.0.1:3333/health", timeout_seconds=1) is True

    probes = []

    class Probe:
        def settimeout(self, value):
            probes.append(value)

        def connect_ex(self, _address):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(sm.socket, "socket", lambda *_args: Probe())
    monotonic_values = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr(sm.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._wait_port_free(port=3334, timeout=1) is False
    monkeypatch.setenv("TRINAXAI_PWA_PORT", "bad")
    monkeypatch.setattr(sm.time, "monotonic", lambda: 2.0)
    assert sm._wait_port_free(timeout=0) is False

    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm, "_service_env", lambda _base: {"TRINAXAI_PORT": "not-a-port"})
    command = sm._rag_command("python", str(tmp_path), {"TRINAXAI_HOST": "not-an-ip"})
    assert command[command.index("--host") + 1] == "127.0.0.1"


def test_service_manager_status_wait_and_windows_specs(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sm.shutil, "which", lambda _name: None)
    assert sm._systemd_set_enabled("rag_api", True) == ""

    monkeypatch.setattr(sm, "_backend", SimpleNamespace())
    assert sm._wait_service_stopped("rag_api") is True

    backend = SimpleNamespace(status=lambda _name: sm.ProcessState("rag_api", False))
    monkeypatch.setattr(sm, "_backend", backend)
    assert sm._wait_service_stopped("rag_api", timeout=1) is True

    monkeypatch.setattr(
        sm, "_backend", SimpleNamespace(status=lambda _name: (_ for _ in ()).throw(RuntimeError("status")))
    )
    assert sm._wait_service_stopped("rag_api", timeout=1) is False

    backend = SimpleNamespace(status=lambda _name: sm.ProcessState("rag_api", True))
    monkeypatch.setattr(sm, "_backend", backend)
    values = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr(sm.time, "monotonic", lambda: next(values))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._wait_service_stopped("rag_api", timeout=1) is False

    monkeypatch.setattr(sm.sys, "platform", "win32")
    monkeypatch.setattr(sm, "_service_env", lambda _base: {"TRINAXAI_FRONTEND_MODE": "dev"})
    monkeypatch.setattr(sm.shutil, "which", lambda name: "npm.exe" if name == "npm" else None)
    monkeypatch.setattr(sm, "_known_windows_executable", lambda name: f"{name}.exe")
    specs = sm._service_specs(str(tmp_path))
    assert specs["trinaxai-frontend"]["command"][1].endswith("vite.js")


def test_service_manager_recovery_and_supervisor_platform_paths(monkeypatch, tmp_path: Path):
    base = str(tmp_path)
    monkeypatch.setattr(sm.sys, "platform", "win32")
    pids = iter([42, 42, None])
    monkeypatch.setattr(sm, "_recovery_pid", lambda _base: next(pids))
    commands = []
    monkeypatch.setattr(sm.subprocess, "run", lambda command, **kwargs: commands.append(command) or _completed())
    clock = iter([0.0, 0.0, 0.0, 6.0])
    monkeypatch.setattr(sm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._stop_recovery(base).detail == "stopped"
    assert commands[0][0] == "taskkill"

    monkeypatch.setattr(sm, "_recovery_pid", lambda _base: None)
    flags = {"CREATE_NEW_PROCESS_GROUP": 1, "DETACHED_PROCESS": 2}
    for name, value in flags.items():
        monkeypatch.setattr(sm.subprocess, name, value, raising=False)
    popen_calls = []
    monkeypatch.setattr(
        sm.subprocess,
        "Popen",
        lambda command, **kwargs: popen_calls.append((command, kwargs)) or SimpleNamespace(pid=9),
    )
    started = sm._start_recovery(base)
    assert started.running and popen_calls[-1][1]["creationflags"] == 3

    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm.subprocess, "Popen", lambda command, **kwargs: popen_calls.append((command, kwargs)))
    sm._start_supervisor(base)
    assert popen_calls[-1][1]["start_new_session"] is True


def test_service_manager_recover_failed_start_and_frontend_health(monkeypatch, tmp_path: Path):
    base = str(tmp_path)
    stopped = []
    monkeypatch.setattr(
        sm, "_backend", SimpleNamespace(stop=lambda name: stopped.append(name) or sm.ProcessState(name, False))
    )
    monkeypatch.setattr(sm, "_ollama_owned_for_stop_all", lambda _base: False)
    monkeypatch.setattr(sm, "_wait_port_free", lambda: True)
    monkeypatch.setattr(sm, "_start_recovery", lambda _base: sm.ProcessState("recovery", True))
    cleanup = sm._recover_failed_start(
        base,
        [
            sm.ProcessState("ollama", False),
            sm.ProcessState("rag_api", False, detail="already running"),
            sm.ProcessState("trinaxai-frontend", False),
        ],
    )
    assert stopped == ["trinaxai-frontend"]
    assert cleanup[-1].name == "recovery"
    monkeypatch.setattr(sm, "_wait_port_free", lambda: False)
    assert (
        sm._recover_failed_start(base, [sm.ProcessState("rag_api", False)])[-1].detail
        == "gateway port remains occupied"
    )

    service = {
        "command": ["frontend"],
        "env": {"TRINAXAI_PWA_PORT": "3334"},
        "log_file": str(tmp_path / "frontend.log"),
    }
    monkeypatch.setattr(
        sm,
        "_backend",
        SimpleNamespace(
            status=lambda name: sm.ProcessState(name, False),
            start=lambda name, **kwargs: sm.ProcessState(name, True, pid=5, detail="started"),
        ),
    )
    monkeypatch.setattr(sm, "_service_specs", lambda _base: {sm.FRONTEND_SERVICE: service})
    monkeypatch.setattr(sm, "_rag_uses_https", lambda *_args: False)
    monkeypatch.setattr(sm, "_wait_for_http", lambda *_args, **_kwargs: True)
    assert sm._start_named(base, sm.FRONTEND_SERVICE).detail.endswith("3334/)")


def test_service_manager_start_reload_and_stop_all_paths(monkeypatch, tmp_path: Path):
    base = str(tmp_path)
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: None)
    monkeypatch.setattr(sm, "_write_service_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sm, "_set_ai_systemd_enabled", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(sm, "_stop_recovery", lambda *_args: sm.ProcessState("recovery", False))
    monkeypatch.setattr(sm, "_recover_failed_start", lambda *_args: [sm.ProcessState("recovery", False)])
    monkeypatch.setattr(
        sm,
        "_start_named",
        lambda _base, name: sm.ProcessState(name, name == "ollama"),
    )
    failed = sm.start_all(base)
    assert failed[-1].name == "recovery"
    started = []
    monkeypatch.setenv("TRINAXAI_START_SUPERVISOR", "1")
    monkeypatch.setattr(sm, "_start_named", lambda _base, name: started.append(name) or sm.ProcessState(name, True))
    monkeypatch.setattr(sm, "_start_supervisor", lambda _base: started.append("supervisor"))
    assert all(item.running for item in sm.start_all(base))
    assert started[-1] == "supervisor"

    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: [sm.ProcessState("reload-network", True)])
    assert sm.reload_network(base)[0].running is True
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: None)
    monkeypatch.setattr(sm.platform, "system", lambda: "Plan9")
    monkeypatch.setattr(sm, "stop_all", lambda: [sm.ProcessState("old", False)])
    monkeypatch.setattr(sm, "start_all", lambda _base: [sm.ProcessState("new", True)])
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert [item.name for item in sm.reload_network(base)] == ["old", "new"]

    monkeypatch.setenv("TRINAXAI_STOP_ALL_DELAY", "bad")
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: [sm.ProcessState("wrapper", False)])
    monkeypatch.setattr(sm, "_set_ai_systemd_enabled", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(sm, "_backend", SimpleNamespace(stop=lambda name: sm.ProcessState(name, False)))
    monkeypatch.setattr(sm, "_wait_service_stopped", lambda _name: True)
    monkeypatch.setattr(sm, "_wait_port_free", lambda: True)
    monkeypatch.setattr(sm, "_start_recovery", lambda _base: sm.ProcessState("recovery", True))
    result = sm.stop_all_for_base(base)
    assert result[-1].name == "recovery"
    monkeypatch.setenv("TRINAXAI_STOP_ALL_DELAY", "0.1")
    assert sm.stop_all_for_base(base)[-1].name == "recovery"


def test_service_manager_autostart_failure_status_watch_and_cli_guard(monkeypatch, tmp_path: Path):
    base = str(tmp_path)
    home = tmp_path / "home"
    monkeypatch.setattr(sm.Path, "home", lambda: home)
    monkeypatch.setattr(sm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None)
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(1, stderr="failed"))
    assert sm.enable_autostart(base).running is False

    monkeypatch.setattr(sm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(1, stderr="load failed"))
    assert sm.enable_autostart(base).running is False

    monkeypatch.setattr(sm, "_backend", SimpleNamespace(status=lambda name: sm.ProcessState(name, True)))
    monkeypatch.setattr(sm, "_system_state", lambda _base: "stopped_by_user")
    monkeypatch.setattr(sm, "_recovery_pid", lambda _base: None)
    monkeypatch.setattr(sm, "_start_recovery", lambda _base: sm.ProcessState("recovery", True, detail="started"))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    sm.watch(base, interval=1)

    monkeypatch.setattr(sm, "_system_state", lambda _base: "running")
    monkeypatch.setattr(sm, "_read_ai_enabled", lambda _base: False)
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: (_ for _ in ()).throw(StopIteration()))
    with pytest.raises(StopIteration):
        sm.watch(base, interval=1)

    monkeypatch.setattr(sm, "_backend", SimpleNamespace(status=lambda name: sm.ProcessState(name, False)))
    assert [item.name for item in sm.status_all()] == sm.SHUTDOWN_ORDER
    assert sm.status("rag_api").running is False

    monkeypatch.setattr(sm, "reload_network", lambda _base: [sm.ProcessState("reload-network", True)])
    assert sm.main(["reload-network", "--base-dir", base]) == 0

    monkeypatch.setattr(sys, "argv", ["service_manager.py", "status", "--base-dir", base])
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(1))
    exits = []
    monkeypatch.setattr(sys, "exit", exits.append)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(Path(sm.__file__)), run_name="__main__")
    assert exc_info.value.code == 0
    assert exits == []
