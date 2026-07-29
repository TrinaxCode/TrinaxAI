from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import service_manager as sm


def _completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr, args=[])


def test_systemctl_uses_passwordless_fallback_and_check(monkeypatch) -> None:
    calls = []
    responses = iter([_completed(1, stderr="denied"), _completed(0)])
    monkeypatch.setattr(sm.subprocess, "run", lambda command, **_kwargs: calls.append(command) or next(responses))
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/sudo" if name == "sudo" else None)

    assert sm._run_systemctl(["start", "rag_api.service"]).returncode == 0
    assert calls[1][:3] == ["sudo", "-n", sm._SYSTEMCTL]

    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(1, stderr="failed"))
    monkeypatch.setattr(sm.shutil, "which", lambda _name: None)
    with pytest.raises(subprocess.CalledProcessError):
        sm._run_systemctl(["start", "missing.service"], check=True)


def test_systemd_backend_start_stop_status_and_direct_fallback(monkeypatch) -> None:
    backend = sm._SystemdBackend()
    monkeypatch.setattr(sm, "_systemd_units", lambda _name: ["primary.service", "legacy.service"])
    responses = iter([_completed(1), _completed(0)])
    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: next(responses))
    assert backend.start("rag_api", command=["python"]).detail.endswith("(legacy.service)")

    responses = iter([_completed(0), _completed(1)])
    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(sm, "_stop_by_name", lambda name: sm.ProcessState(name, False, detail="processes stopped"))
    stopped = backend.stop("rag_api")
    assert "primary.service" in stopped.detail and "processes stopped" in stopped.detail

    responses = iter([_completed(0), _completed(0, stdout="123\n")])
    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: next(responses))
    assert backend.status("rag_api").pid == 123

    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(sm, "_start_direct", lambda name, **_kwargs: sm.ProcessState(name, True, pid=5))
    assert backend.start("rag_api", command=["python"]).pid == 5


def test_launchctl_backend_loads_existing_plist_and_falls_back(monkeypatch, tmp_path: Path) -> None:
    label = "com.trinaxai.rag_api"
    plist = tmp_path / "Library" / "LaunchAgents" / f"{label}.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("", encoding="utf-8")
    monkeypatch.setattr(sm.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed())
    backend = sm._LaunchctlBackend()

    assert backend.start("rag_api", command=["python"]).running is True
    assert backend.status("rag_api").running is True
    assert backend.stop("rag_api").running is False

    plist.unlink()
    monkeypatch.setattr(sm, "_start_direct", lambda name, **_kwargs: sm.ProcessState(name, True, pid=9))
    assert backend.start("rag_api", command=["python"]).pid == 9


def test_direct_process_status_stop_and_start_failure_are_safe(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sm.sys, "platform", "linux")
    responses = iter([_completed(1), _completed(0, stdout="321\n")])
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: next(responses))
    assert sm._pgrep_status("rag_api").pid == 321

    calls = []
    monkeypatch.setattr(sm.subprocess, "run", lambda command, **_kwargs: calls.append(command) or _completed())
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._stop_by_name("rag_api").running is False
    assert any("-TERM" in command for command in calls)
    assert any("-KILL" in command for command in calls)

    log = tmp_path / "service.log"
    monkeypatch.setattr(sm.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")))
    result = sm._start_direct("rag_api", command=["python"], log_file=str(log))
    assert result.running is False and "denied" in result.detail


@pytest.mark.parametrize(
    ("system", "systemctl", "backend_type"),
    [
        ("Linux", "/usr/bin/systemctl", sm._SystemdBackend),
        ("Linux", None, sm._DirectBackend),
        ("Darwin", None, sm._LaunchctlBackend),
        ("Windows", None, sm._DirectBackend),
    ],
)
def test_backend_detection(monkeypatch, system: str, systemctl: str | None, backend_type: type) -> None:
    monkeypatch.setattr(sm.platform, "system", lambda: system)
    monkeypatch.setattr(sm.shutil, "which", lambda name: systemctl if name == "systemctl" else None)
    assert isinstance(sm._detect_backend(), backend_type)


def test_service_specs_cover_posix_and_windows_production(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm.shutil, "which", lambda name: f"/usr/bin/{name}")
    specs = sm._service_specs(str(tmp_path))
    assert specs["trinaxai-frontend"]["command"] == ["/usr/bin/npm", "run", "serve"]
    assert specs["ollama"]["command"][0] == "/usr/bin/ollama"

    monkeypatch.setattr(sm.sys, "platform", "win32")
    monkeypatch.setattr(sm, "_known_windows_executable", lambda name: f"C:/{name}.exe")
    specs = sm._service_specs(str(tmp_path))
    assert specs["trinaxai-frontend"]["command"][-1].endswith("server.mjs")


def test_start_named_reports_health_ready_pending_and_early_exit(monkeypatch, tmp_path: Path) -> None:
    backend = SimpleNamespace(
        status=lambda _name: sm.ProcessState("rag_api", False),
        start=lambda name, **_kwargs: sm.ProcessState(name, True, pid=10, detail="started"),
    )
    monkeypatch.setattr(sm, "_backend", backend)
    monkeypatch.setattr(sm, "_service_specs", lambda _base: {"rag_api": {"command": ["python"], "env": {}}})
    monkeypatch.setattr(sm, "_rag_health_url", lambda *_args: "http://127.0.0.1:3333/health")
    monkeypatch.setattr(sm, "_wait_for_http", lambda *_args, **_kwargs: True)
    assert "health ok" in sm._start_named(str(tmp_path), "rag_api").detail

    monkeypatch.setattr(sm, "_wait_for_http", lambda *_args, **_kwargs: False)
    pending_statuses = iter([sm.ProcessState("rag_api", False), sm.ProcessState("rag_api", True, pid=11)])
    backend.status = lambda _name: next(pending_statuses)
    assert "not ready yet" in sm._start_named(str(tmp_path), "rag_api").detail
    backend.status = lambda _name: sm.ProcessState("rag_api", False)
    assert "exited before health" in sm._start_named(str(tmp_path), "rag_api").detail

    backend.status = lambda _name: sm.ProcessState("rag_api", True, pid=12, detail="existing")
    assert "already running" in sm._start_named(str(tmp_path), "rag_api").detail


def test_public_lifecycle_orders_services_and_honors_privileged_wrapper(monkeypatch, tmp_path: Path) -> None:
    started = []
    stopped = []
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: None)
    monkeypatch.setattr(sm, "_write_ai_enabled", lambda *_args: None)
    monkeypatch.setattr(sm, "_set_ai_systemd_enabled", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(sm, "_start_named", lambda _base, name: started.append(name) or sm.ProcessState(name, True))
    monkeypatch.setattr(sm, "_stop_named", lambda name: stopped.append(name) or sm.ProcessState(name, False))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)

    assert [item.name for item in sm.start_all(str(tmp_path))] == sm.STARTUP_ORDER
    assert [item.name for item in sm.start_frontend(str(tmp_path))] == [sm.FRONTEND_SERVICE]
    assert [item.name for item in sm.stop_ai(str(tmp_path))] == sm.AI_SHUTDOWN_ORDER

    elevated = [sm.ProcessState("start-ai", True)]
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: elevated)
    assert sm.start_ai(str(tmp_path)) is elevated

    backend = SimpleNamespace(stop=lambda name: sm.ProcessState(name, False))
    monkeypatch.setattr(sm, "_backend", backend)
    assert [item.name for item in sm.stop_all()] == sm.FULL_SHUTDOWN_ORDER


def test_privileged_wrapper_and_systemd_enable_failures(monkeypatch, tmp_path: Path) -> None:
    wrapper = tmp_path / "wrapper"
    wrapper.write_text("", encoding="utf-8")
    wrapper.chmod(0o700)
    monkeypatch.setattr(sm, "PRIVILEGED_LIFECYCLE_WRAPPER", wrapper)
    monkeypatch.setattr(sm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sm.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(sm.os, "access", lambda *_args: True)
    monkeypatch.setattr(sm.shutil, "which", lambda _name: "/usr/bin/tool")
    monkeypatch.setattr(sm, "_write_ai_enabled", lambda *_args: None)
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed(0, stdout="ok"))
    assert sm._try_privileged_wrapper(str(tmp_path), "stop-ai")[0].running is False

    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: _completed(1, stderr="denied"))
    assert "failed" in sm._systemd_set_enabled("rag_api", False, stop_now=True)


def test_linux_and_windows_autostart_round_trip(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(sm.Path, "home", lambda: home)
    monkeypatch.setattr(sm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sm.shutil, "which", lambda _name: "/usr/bin/systemctl")
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed())
    enabled = sm.enable_autostart(str(tmp_path))
    assert enabled.running is True
    assert (home / ".config" / "systemd" / "user" / "trinaxai.service").exists()
    assert sm.disable_autostart(str(tmp_path)).running is False

    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr(sm.platform, "system", lambda: "Windows")
    monkeypatch.setattr(sm, "_windows_hidden_python", lambda value: value)
    enabled = sm.enable_autostart(str(tmp_path))
    assert enabled.running is True
    assert "TrinaxAI.vbs" in enabled.detail
    assert sm.disable_autostart(str(tmp_path)).running is False


def test_supervisor_restarts_wanted_services_once(monkeypatch, tmp_path: Path) -> None:
    statuses = []
    monkeypatch.setattr(sm, "_read_ai_enabled", lambda _base: False)
    monkeypatch.setattr(sm, "_reap_zombie_children", lambda: None)
    monkeypatch.setattr(
        sm,
        "_backend",
        SimpleNamespace(status=lambda name: statuses.append(name) or sm.ProcessState(name, False)),
    )
    monkeypatch.setattr(sm, "_start_named", lambda _base, name: sm.ProcessState(name, True, detail="restarted"))
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: (_ for _ in ()).throw(StopIteration()))

    with pytest.raises(StopIteration):
        sm.watch(str(tmp_path), interval=5)
    assert statuses == [sm.FRONTEND_SERVICE]


def test_service_manager_cli_dispatches_every_public_action(monkeypatch, tmp_path: Path, capsys) -> None:
    running = sm.ProcessState("rag_api", True, pid=3, detail="ready")
    stopped = sm.ProcessState("rag_api", False, detail="stopped")
    monkeypatch.setattr(sm, "start_all", lambda _base: [running])
    monkeypatch.setattr(sm, "start_ai", lambda _base: [running])
    monkeypatch.setattr(sm, "start_frontend", lambda _base: [running])
    monkeypatch.setattr(sm, "stop_ai", lambda _base: [stopped])
    monkeypatch.setattr(sm, "stop_all_for_base", lambda _base: [stopped])
    monkeypatch.setattr(sm, "status_all", lambda: [running])
    monkeypatch.setattr(sm, "watch", lambda _base, _interval: None)
    monkeypatch.setattr(sm, "enable_autostart", lambda _base: sm.ProcessState("autostart", True, detail="enabled"))
    monkeypatch.setattr(sm, "disable_autostart", lambda _base: sm.ProcessState("autostart", False, detail="disabled"))
    base = ["--base-dir", str(tmp_path)]

    for action in ("start", "start-ai", "start-frontend", "stop", "stop-ai", "stop-all", "watch"):
        assert sm.main([action, *base]) == 0

    assert sm.main(["status", "--json", *base]) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload[0]["display_name"] == "TrinaxAI RAG API"
    assert payload[0]["running"] is True

    assert sm.main(["enable-autostart", *base]) == 0
    assert sm.main(["disable-autostart", *base]) == 0


def test_direct_backend_and_windows_process_paths(monkeypatch, tmp_path: Path) -> None:
    class StartupInfo:
        dwFlags = 0
        wShowWindow = 1

    monkeypatch.setattr(sm.sys, "platform", "win32")
    monkeypatch.setattr(sm.subprocess, "STARTUPINFO", StartupInfo, raising=False)
    monkeypatch.setattr(sm.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(sm.subprocess, "CREATE_NO_WINDOW", 2, raising=False)
    assert sm._windows_no_window_kwargs()["creationflags"] == 2

    calls = []
    monkeypatch.setattr(
        sm.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or _completed(stdout="4321\n"),
    )
    status = sm._pgrep_status("rag_api")
    assert status.running and status.pid == 4321
    stopped = sm._stop_by_name("rag_api")
    assert stopped.running is False
    assert any(command[0] == "powershell" for command, _kwargs in calls)

    class Process:
        pid = 77

    monkeypatch.setattr(sm.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    started = sm._start_direct(
        "rag_api",
        command=["python"],
        cwd=str(tmp_path),
        env={"TEST_FLAG": "yes"},
        log_file=str(tmp_path / "rag.log"),
    )
    assert started.pid == 77

    direct = sm._DirectBackend()
    monkeypatch.setattr(sm, "_start_direct", lambda name, **_kwargs: sm.ProcessState(name, True, pid=8))
    monkeypatch.setattr(sm, "_stop_by_name", lambda name: sm.ProcessState(name, False))
    monkeypatch.setattr(sm, "_pgrep_status", lambda name: sm.ProcessState(name, True, pid=8))
    assert direct.start("rag_api", command=["python"]).pid == 8
    assert direct.stop("rag_api").running is False
    assert direct.status("rag_api").running is True


def test_process_helpers_cover_fallbacks_and_zombie_reaping(monkeypatch) -> None:
    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(
        sm.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("pgrep", 1)),
    )
    assert sm._pgrep_status("missing").detail == "pgrep/tasklist unavailable"

    calls = []
    responses = iter([_completed(), _completed()])
    monkeypatch.setattr(
        sm.subprocess,
        "run",
        lambda command, **_kwargs: calls.append(command) or next(responses),
    )
    monkeypatch.setattr(sm, "PROCESS_PATTERNS", {"custom": ["one"]})
    monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)
    assert sm._stop_by_name("custom").running is False

    waited = iter([(9, 0), (0, 0)])
    monkeypatch.setattr(sm.os, "waitpid", lambda *_args: next(waited))
    monkeypatch.setattr(sm.os, "WNOHANG", 1, raising=False)
    sm._reap_zombie_children()

    monkeypatch.setattr(sm.os, "waitpid", lambda *_args: (_ for _ in ()).throw(ChildProcessError()))
    sm._reap_zombie_children()
    monkeypatch.setattr(sm.os, "waitpid", lambda *_args: (_ for _ in ()).throw(OSError()))
    sm._reap_zombie_children()


def test_environment_https_and_rag_command_helpers(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# comment\nEMPTY\nTRINAXAI_PORT='4444'\nTRINAXAI_HOST=0.0.0.0\n",
        encoding="utf-8",
    )
    values = sm._read_env_file(str(tmp_path))
    assert values["TRINAXAI_PORT"] == "4444"
    monkeypatch.setenv("TRINAXAI_PORT", "5555")
    assert sm._service_env(str(tmp_path))["TRINAXAI_PORT"] == "5555"
    assert sm._frontend_script({"TRINAXAI_FRONTEND_MODE": "DEV"}) == "dev"
    assert sm._frontend_script({"TRINAXAI_FRONTEND_MODE": "other"}) == "serve"

    cert_dir = tmp_path / "chat-pwa" / "certs"
    cert_dir.mkdir(parents=True)
    (cert_dir / "localhost-key.pem").write_text("key", encoding="utf-8")
    (cert_dir / "localhost.pem").write_text("cert", encoding="utf-8")
    assert sm._rag_https_files(str(tmp_path))
    command = sm._rag_command(
        "python",
        str(tmp_path),
        {"TRINAXAI_HOST": "0.0.0.0", "TRINAXAI_PORT": "4444"},
    )
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert "--ssl-keyfile" in command
    unsafe = sm._rag_command(
        "python",
        str(tmp_path),
        {"TRINAXAI_HOST": "0.0.0.0", "TRINAXAI_UNSAFE_BIND_BACKEND": "yes"},
    )
    assert unsafe[unsafe.index("--host") + 1] == "0.0.0.0"

    assert sm._wait_for_http("file:///etc/passwd", timeout_seconds=0) is False
    assert sm._wait_for_http("http://example.com", timeout_seconds=0) is False
    assert sm._rag_health_url(str(tmp_path), {"TRINAXAI_PORT": "4444"}).startswith("https://")


def test_service_state_wrapper_and_platform_autostart_edges(monkeypatch, tmp_path: Path) -> None:
    assert sm._read_ai_enabled(str(tmp_path)) is True
    sm._write_ai_enabled(str(tmp_path), False)
    assert sm._read_ai_enabled(str(tmp_path)) is False

    monkeypatch.setattr(sm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sm.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(sm.shutil, "which", lambda _name: "/usr/bin/tool")
    monkeypatch.setattr(sm, "PRIVILEGED_LIFECYCLE_WRAPPER", tmp_path / "missing")
    assert sm._try_privileged_wrapper(str(tmp_path), "start-ai") is None
    assert sm._try_privileged_wrapper(str(tmp_path), "invalid") is None

    home = tmp_path / "home"
    monkeypatch.setattr(sm.Path, "home", lambda: home)
    monkeypatch.setattr(sm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sm.subprocess, "run", lambda *_args, **_kwargs: _completed())
    enabled = sm.enable_autostart(str(tmp_path))
    assert enabled.running is True
    plist = home / "Library" / "LaunchAgents" / "com.trinaxcode.trinaxai.plist"
    assert plist.exists()
    assert sm.disable_autostart(str(tmp_path)).running is False
    assert not plist.exists()

    monkeypatch.setattr(sm.platform, "system", lambda: "Plan9")
    assert sm.enable_autostart(str(tmp_path)).running is False
    assert sm.disable_autostart(str(tmp_path)).detail == "autostart backend unavailable"


def test_windows_executable_and_systemd_status_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sm.sys, "platform", "linux")
    assert sm._windows_hidden_python("/usr/bin/python") == "/usr/bin/python"

    monkeypatch.setattr(sm.sys, "platform", "win32")
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")
    assert sm._windows_hidden_python(str(python)) == str(pythonw)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    ollama = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    ollama.parent.mkdir(parents=True)
    ollama.write_text("", encoding="utf-8")
    monkeypatch.setattr(sm.shutil, "which", lambda _name: None)
    assert sm._known_windows_executable("ollama") == str(ollama)
    assert sm._known_windows_executable("unknown") is None

    backend = sm._SystemdBackend()
    monkeypatch.setattr(sm, "_systemd_units", lambda _name: ["rag.service"])
    responses = iter([_completed(0), _completed(0, stdout="not-a-pid")])
    monkeypatch.setattr(sm, "_run_systemctl", lambda *_args, **_kwargs: next(responses))
    assert backend.status("rag_api").running is True
    monkeypatch.setattr(
        sm,
        "_run_systemctl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("systemctl", 1)),
    )
    monkeypatch.setattr(sm, "_pgrep_status", lambda name: sm.ProcessState(name, False))
    assert backend.status("rag_api").running is False
