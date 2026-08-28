from __future__ import annotations

import os
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from trinaxai_cli import app, branding, i18n, network, processes, prompts, router, runtime, session
from trinaxai_cli import config as cli_config


def test_cli_branding_platform_and_rich_fallback_edges(monkeypatch) -> None:
    monkeypatch.setattr(branding.os, "get_terminal_size", lambda: (_ for _ in ()).throw(OSError()))
    assert branding._terminal_width(73) == 73
    monkeypatch.setattr(branding.sys.stdout, "isatty", lambda: (_ for _ in ()).throw(RuntimeError()))
    assert branding._is_tty() is False
    monkeypatch.setattr(branding, "_is_tty", lambda: False)
    branding.clear_terminal()

    monkeypatch.setattr(branding, "_is_tty", lambda: True)
    monkeypatch.setattr(branding.os, "name", "nt")
    cleared = []
    monkeypatch.setattr(branding.os, "system", cleared.append)
    branding.clear_terminal()
    assert cleared == ["cls"]

    monkeypatch.setattr(branding.os, "name", "posix")
    stdout = SimpleNamespace(write=lambda _value: (_ for _ in ()).throw(OSError()), flush=lambda: None)
    monkeypatch.setattr(branding.sys, "stdout", stdout)
    branding.clear_terminal()

    class RichConsole:
        def __init__(self, broken: bool = False):
            self.printed = []
            self.broken = broken

        def print(self, value, **_kwargs):
            if self.broken:
                raise RuntimeError("render failed")
            self.printed.append(value)

    rich = RichConsole()
    lines = []
    ui = SimpleNamespace(_rich_console=rich, _color_enabled=True, print=lines.append)
    branding.render_banner(ui, subtitle="Ready")
    assert rich.printed and any("Ready" in str(value) for value in rich.printed)

    fallback_lines = []
    branding.render_banner(
        SimpleNamespace(_rich_console=RichConsole(broken=True), _color_enabled=True, print=fallback_lines.append)
    )
    assert fallback_lines

    monkeypatch.setenv("NO_COLOR", "1")
    branding.set_terminal_title("ignored")
    monkeypatch.delenv("NO_COLOR")
    title_output = []
    monkeypatch.setattr(branding.sys, "stdout", SimpleNamespace(write=title_output.append, flush=lambda: None))
    branding.set_terminal_title("ready")
    assert title_output
    failing_stdout = SimpleNamespace(write=lambda _value: (_ for _ in ()).throw(OSError()), flush=lambda: None)
    monkeypatch.setattr(branding.sys, "stdout", failing_stdout)
    branding.set_terminal_title("ignored")


def test_cli_config_i18n_router_runtime_and_session_edges(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(cli_config.sys, "platform", "win32")
    assert "TrinaxAI" in str(cli_config._default_config_path())
    monkeypatch.setattr(cli_config.sys, "platform", "darwin")
    assert "Application Support" in str(cli_config._default_config_path())
    monkeypatch.setattr(cli_config.sys, "platform", "linux")
    assert ".config" in str(cli_config._default_config_path())
    monkeypatch.setattr(cli_config.CLIConfig, "find_config", classmethod(lambda _cls: None))
    assert isinstance(cli_config.CLIConfig.load(), cli_config.CLIConfig)
    assert cli_config._parse_scalar("") == ""
    assert cli_config._parse_scalar("unquoted") == "unquoted"

    for name in ("TRINAXAI_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    assert i18n.detect_lang() == "en"
    assert i18n.text("missing-key") == "missing-key"
    assert i18n.translate(123, "es") == 123
    assert i18n.translate("not translated", "es") == "not translated"

    assert prompts.should_think_for_turn("implement a complete solution with tests") is True
    assert prompts.should_think_for_turn("what is dependency injection") is False
    assert prompts.should_think_for_turn("prove this step by step") is True
    assert prompts.should_think_for_turn("anything", enabled=False) is False
    assert prompts.detect_lang("¿") == "es"
    creator_messages = [{"role": "user", "content": "who created you?"}]
    assert prompts._wants_creator_facts(creator_messages)
    assert len(prompts.general_system_messages(creator_messages)) == 2
    assert prompts.creator_facts_message(creator_messages)
    assert prompts._wants_creator_facts([]) is False
    assert prompts._wants_creator_facts([*creator_messages, {"role": "user", "content": "links"}])
    assert prompts.creator_facts_message([{"role": "user", "content": "hello"}]) is None
    assert "Analyze" in prompts.vision_system_messages([{"role": "user", "content": "hello"}], "en")[0]["content"]

    assert router.decide_mode("anything", router.RouteContext(research_mode=True)).mode == "deep_research"
    assert router.decide_mode("anything", router.RouteContext(engine="rag")).mode == "rag"
    assert router.decide_mode("my files").mode == "rag"

    monkeypatch.setenv("TRINAXAI_HOME", str(tmp_path))
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda _cls: tmp_path))
    windows_candidates = runtime.install_candidates()
    assert tmp_path / "local" / "TrinaxAI" in windows_candidates
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    mac_candidates = runtime.install_candidates()
    assert tmp_path / "Library" / "Application Support" / "TrinaxAI" in mac_candidates

    assert session.Session.load("missing", tmp_path) == []
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert session._default_session_dir().name == "sessions"
    assert session._resolve_dir(None) == session._default_session_dir()
    session_path = tmp_path / "history"
    with session.Session("chat/name", session_path) as saved:
        saved.append("user", "hola")
    file_path = session_path / "chat_name.jsonl"
    file_path.write_text(file_path.read_text(encoding="utf-8") + "\nnot-json\n", encoding="utf-8")
    assert len(session.Session.load("chat/name", session_path)) == 1
    assert session.Session.delete("missing", session_path) is False
    assert session.Session.delete("chat/name", session_path) is True
    assert "malformed" in capsys.readouterr().err


def test_cli_network_and_process_cleanup_edges(monkeypatch, tmp_path: Path) -> None:
    class BadSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def connect(self, _target):
            raise OSError("unrouted")

    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("bad", 0))])
    monkeypatch.setattr(network.socket, "socket", lambda *_args, **_kwargs: BadSocket())
    assert network.lan_addresses() == []
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert network.lan_addresses() == []

    monkeypatch.setattr(network.shutil, "which", lambda name: "/bin/mkcert" if name == "mkcert" else None)
    monkeypatch.setattr(network.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")))
    assert network.trust_certificate(tmp_path) is None

    def which(name):
        return f"/bin/{name}" if name in {"mkcert", "openssl"} else None

    def failing_pfx(command, **_kwargs):
        if "pkcs12" in command:
            return SimpleNamespace(returncode=1, stderr="pfx failed", stdout="")
        Path(command[command.index("-cert-file") + 1]).write_text("cert", encoding="utf-8")
        Path(command[command.index("-key-file") + 1]).write_text("key", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(network.shutil, "which", which)
    monkeypatch.setattr(network.subprocess, "run", failing_pfx)
    monkeypatch.setattr(network.platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError, match="pfx failed"):
        network.refresh_certificate(tmp_path, [])

    def successful_mkcert(command, **_kwargs):
        Path(command[command.index("-cert-file") + 1]).write_text("cert", encoding="utf-8")
        Path(command[command.index("-key-file") + 1]).write_text("key", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(network.shutil, "which", lambda name: "/bin/mkcert" if name == "mkcert" else None)
    monkeypatch.setattr(network.subprocess, "run", successful_mkcert)
    network.refresh_certificate(tmp_path, [])
    assert not (tmp_path / "chat-pwa" / "certs" / "trinaxai-local.pfx").exists()

    class StubbornProcess:
        pid = 42

        def __init__(self):
            self.terminated = 0
            self.killed = 0
            self.wait_calls = 0

        def poll(self):
            return None

        def terminate(self):
            self.terminated += 1

        def kill(self):
            self.killed += 1

        def wait(self, timeout=None):
            self.wait_calls += 1
            raise subprocess.TimeoutExpired("worker", timeout)

    monkeypatch.setattr(processes.sys, "platform", "linux")
    monkeypatch.delattr(processes.os, "killpg", raising=False)
    stubborn = StubbornProcess()
    processes.terminate_process_group(stubborn, grace_seconds=0.01)
    assert stubborn.terminated == 1 and stubborn.killed == 1

    class WindowsProcess(StubbornProcess):
        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("worker", timeout)
            return 0

    monkeypatch.setattr(processes.sys, "platform", "win32")
    monkeypatch.setattr(processes.subprocess, "run", lambda *_args, **_kwargs: None)
    windows_process = WindowsProcess()
    processes.terminate_process_group(windows_process, grace_seconds=0.01)
    assert windows_process.killed == 1

    class InterruptedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            if timeout is not None:
                raise KeyboardInterrupt
            return "", ""

    interrupted = InterruptedProcess()
    terminated = []
    monkeypatch.setattr(processes, "spawn_process_group", lambda *_args, **_kwargs: interrupted)
    monkeypatch.setattr(processes, "terminate_process_group", terminated.append)
    with pytest.raises(KeyboardInterrupt):
        processes.run_process_group(["worker"], timeout=1)
    assert terminated == [interrupted]


def test_cli_app_entrypoints_dispatch_and_validation(monkeypatch, tmp_path: Path) -> None:
    parser = app._build_parser(language="es")
    assert "CLI de TrinaxAI" in parser.format_help()
    monkeypatch.setattr(app.sys, "argv", ["trinaxai", "--language", "es", "version"])
    assert app._build_parser().language == "es"

    monkeypatch.setattr(app, "get_console", lambda **_kwargs: object())
    monkeypatch.setattr(app.CLIConfig, "find_config", classmethod(lambda _cls: None))
    monkeypatch.setattr(app.CLIConfig, "load", classmethod(lambda _cls, _path=None: cli_config.CLIConfig()))
    monkeypatch.setattr(
        app.importlib,
        "import_module",
        lambda _name: SimpleNamespace(run=lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    ui = SimpleNamespace(failure=lambda *_args: None, error=lambda *_args: None, warn=lambda *_args: None)
    monkeypatch.setattr(app.LOG, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(app.LOG, "exception", lambda *_args: None)
    assert app._dispatch("broken", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 1

    monkeypatch.setattr(app.importlib, "import_module", lambda _name: (_ for _ in ()).throw(ImportError("missing")))
    assert app._dispatch("missing", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 1
    monkeypatch.setattr(app.importlib, "import_module", lambda _name: SimpleNamespace())
    assert app._dispatch("empty", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 1
    monkeypatch.setattr(
        app.importlib,
        "import_module",
        lambda _name: SimpleNamespace(run=lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt())),
    )
    assert app._dispatch("interrupt", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 130
    monkeypatch.setattr(
        app.importlib,
        "import_module",
        lambda _name: SimpleNamespace(run=lambda *_args: (_ for _ in ()).throw(SystemExit(7))),
    )
    assert app._dispatch("exit", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 7
    monkeypatch.setattr(app.importlib, "import_module", lambda _name: SimpleNamespace(run=lambda *_args: None))
    assert app._dispatch("none", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 0
    monkeypatch.setattr(app.importlib, "import_module", lambda _name: SimpleNamespace(run=lambda *_args: "bad"))
    assert app._dispatch("bad-result", SimpleNamespace(), None, ui, cli_config.CLIConfig()) == 1

    monkeypatch.setattr(app, "_dispatch", lambda *_args: 0)
    assert app.main(["--install-root", str(tmp_path), "version"]) == 0
    assert os.environ["TRINAXAI_HOME"] == str(tmp_path)

    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("certificate", encoding="utf-8")
    assert app.main(["--ca-file", str(ca_file), "version"]) == 0

    with pytest.raises(SystemExit) as missing_ca:
        app.main(["--ca-file", str(tmp_path / "missing.pem"), "version"])
    assert missing_ca.value.code == 2

    monkeypatch.setattr(
        app.CLIConfig, "load", classmethod(lambda _cls, _path=None: cli_config.CLIConfig(api_verify_tls=False))
    )
    with pytest.raises(SystemExit) as insecure:
        app.main(["version"])
    assert insecure.value.code == 2

    monkeypatch.setattr(app.CLIConfig, "load", classmethod(lambda _cls, _path=None: cli_config.CLIConfig()))
    from trinaxai_cli import client as client_module

    class Client:
        def __init__(self, **_kwargs):
            self.closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(client_module, "TrinaxAPIClient", Client)
    assert app.main(["chat"]) == 0

    monkeypatch.setattr(app, "main", lambda: 0)
    with pytest.raises(SystemExit) as module_exit:
        runpy.run_path(str(Path(__file__).parents[1] / "trinaxai_cli" / "__main__.py"), run_name="__main__")
    assert module_exit.value.code == 0
