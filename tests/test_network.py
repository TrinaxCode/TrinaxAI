from pathlib import Path
from types import SimpleNamespace

import pytest

from trinaxai_cli import network
from trinaxai_cli.commands import network as network_command


class UI:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, value: str) -> None:
        self.messages.append(value)

    info = print
    warn = print
    error = print
    success = print

    def failure(self, label: str, exc: Exception) -> None:
        self.messages.append(f"{label}: {exc}")

    def confirm(self, *_args, **_kwargs) -> bool:
        return True


def test_network_origins_include_stable_hostname_and_current_address(monkeypatch) -> None:
    monkeypatch.setattr(network.socket, "gethostname", lambda: "Trinax-Host")
    origins = network.cors_origins(["192.168.0.18"])
    urls = network.pwa_urls(["192.168.0.18"])
    assert "https://Trinax-Host.local:3334" in origins
    assert "https://192.168.0.18:3334" in origins
    assert urls == ["https://192.168.0.18:3334", "https://Trinax-Host.local:3334"]


def test_update_env_replaces_stale_network_without_touching_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(network.socket, "gethostname", lambda: "trinax")
    env = tmp_path / ".env"
    env.write_text(
        "TRINAXAI_ADMIN_TOKEN=keep-me\nTRINAXAI_CORS_ORIGINS=https://old-router.local:3334\n", encoding="utf-8"
    )
    env.chmod(0o600)
    # Windows ignores POSIX mode bits, so assert the mode is preserved rather
    # than hardcoding 0o600: that also catches a widened secrets file there.
    mode_before = env.stat().st_mode
    network.update_env(tmp_path, ["192.168.0.18"])
    updated = env.read_text(encoding="utf-8")
    assert "TRINAXAI_ADMIN_TOKEN=keep-me" in updated
    assert "old-router.local" not in updated
    assert "192.168.0.18" in updated
    assert env.stat().st_mode == mode_before


def test_update_env_appends_missing_origin_and_rejects_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("TRINAXAI_ADMIN_TOKEN=keep-me\n", encoding="utf-8")
    network.update_env(tmp_path, ["192.168.0.18"])
    assert "TRINAXAI_CORS_ORIGINS=" in env.read_text(encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        network.update_env(tmp_path / "missing", [])


def test_refresh_command_updates_https_and_restarts(monkeypatch, tmp_path: Path) -> None:
    ui = UI()
    calls: list[object] = []
    monkeypatch.setattr(network_command._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        network_command._system, "run_service_action", lambda action, _ui, timeout: calls.append((action, timeout)) or 0
    )
    monkeypatch.setattr(network, "lan_addresses", lambda: ["192.168.0.18"])
    monkeypatch.setattr(network, "refresh_certificate", lambda root, addresses: calls.append((root, addresses)))
    monkeypatch.setattr(network, "update_env", lambda root, addresses: calls.append((root, addresses, "env")))
    monkeypatch.setattr(network, "pwa_urls", lambda _addresses: ["https://trinax.local:3334"])
    result = network_command.run(SimpleNamespace(network_command="refresh", yes=True, no_restart=False), None, ui, None)
    assert result == 0
    assert ("reload-network", 180) in calls
    assert "https://trinax.local:3334" in ui.messages


def test_lan_addresses_prefers_the_routed_private_address(monkeypatch) -> None:
    class Probe:
        def __init__(self, family: int, *_args) -> None:
            self.family = family

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def connect(self, _target) -> None:
            if self.family == network.socket.AF_INET6:
                raise OSError("no IPv6 route")

        def getsockname(self):
            return ("192.168.0.18", 0)

    monkeypatch.setattr(network.socket, "socket", Probe)
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("172.17.0.1", 0))],
    )
    assert network.lan_addresses() == ["192.168.0.18"]


@pytest.mark.parametrize("system", ["Linux", "Windows"])
def test_refresh_certificate_writes_all_runtime_formats(tmp_path: Path, monkeypatch, system: str) -> None:
    def which(name: str):
        return f"/bin/{name}"

    def run(command, **_kwargs):
        if "pkcs12" in command:
            Path(command[command.index("-out") + 1]).write_bytes(b"pfx")
        else:
            Path(command[command.index("-cert-file") + 1]).write_text("certificate", encoding="utf-8")
            Path(command[command.index("-key-file") + 1]).write_text("key", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(network.shutil, "which", which)
    monkeypatch.setattr(network.subprocess, "run", run)
    monkeypatch.setattr(network.platform, "system", lambda: system)
    monkeypatch.setattr(network.socket, "gethostname", lambda: "trinax")
    network.refresh_certificate(tmp_path, ["192.168.0.18"])
    cert_dir = tmp_path / "chat-pwa" / "certs"
    assert (cert_dir / "localhost.pem").read_text(encoding="utf-8") == "certificate"
    assert (cert_dir / "trinaxai-local.crt").is_file()
    assert (cert_dir / "trinaxai-local.pfx").is_file() is (system == "Windows")


def test_refresh_certificate_falls_back_to_openssl(tmp_path: Path, monkeypatch) -> None:
    def run(command, **_kwargs):
        Path(command[command.index("-out") + 1]).write_text("certificate", encoding="utf-8")
        Path(command[command.index("-keyout") + 1]).write_text("key", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(network.shutil, "which", lambda name: None if name == "mkcert" else "/bin/openssl")
    monkeypatch.setattr(network.subprocess, "run", run)
    # Pin the platform: on Windows the extra PFX export call carries no -keyout.
    monkeypatch.setattr(network.platform, "system", lambda: "Linux")
    network.refresh_certificate(tmp_path, ["192.168.0.18"])
    assert (tmp_path / "chat-pwa" / "certs" / "localhost.pem").is_file()


def test_refresh_certificate_reports_missing_tool_and_generation_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(network.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="mkcert or OpenSSL"):
        network.refresh_certificate(tmp_path, [])

    monkeypatch.setattr(network.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        network.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="generation failed", stdout=""),
    )
    with pytest.raises(RuntimeError, match="generation failed"):
        network.refresh_certificate(tmp_path, [])


def test_refresh_command_handles_status_cancel_missing_network_and_no_restart(monkeypatch, tmp_path: Path) -> None:
    ui = UI()
    monkeypatch.setattr(network_command._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(network, "lan_addresses", lambda: ["192.168.0.18"])
    monkeypatch.setattr(network, "pwa_urls", lambda _addresses: ["https://trinax.local:3334"])
    monkeypatch.setattr(network, "local_hostname", lambda: "trinax")
    assert network_command.run(SimpleNamespace(network_command=None), None, ui, None) == 0

    ui.confirm = lambda *_args, **_kwargs: False
    assert network_command.run(SimpleNamespace(network_command="refresh", yes=False), None, ui, None) == 0

    monkeypatch.setattr(network, "lan_addresses", lambda: [])
    assert network_command.run(SimpleNamespace(network_command="refresh", yes=True), None, ui, None) == 1

    monkeypatch.setattr(network, "lan_addresses", lambda: ["192.168.0.18"])
    monkeypatch.setattr(network, "refresh_certificate", lambda *_args: None)
    monkeypatch.setattr(network, "update_env", lambda *_args: None)
    assert (
        network_command.run(SimpleNamespace(network_command="refresh", yes=True, no_restart=True), None, ui, None) == 0
    )


def test_refresh_command_reports_missing_install_and_generation_failure(monkeypatch, tmp_path: Path) -> None:
    ui = UI()
    monkeypatch.setattr(network_command._system, "project_root", lambda: None)
    assert network_command.run(SimpleNamespace(network_command=None), None, ui, None) == 1

    monkeypatch.setattr(network_command._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(network, "lan_addresses", lambda: ["192.168.0.18"])
    monkeypatch.setattr(network, "pwa_urls", lambda _addresses: [])
    monkeypatch.setattr(network, "refresh_certificate", lambda *_args: (_ for _ in ()).throw(RuntimeError("failed")))
    assert network_command.run(SimpleNamespace(network_command="refresh", yes=True), None, ui, None) == 1
    assert any("failed" in message for message in ui.messages)


def test_refresh_command_uses_linux_restart_fallback(monkeypatch, tmp_path: Path) -> None:
    ui = UI()
    monkeypatch.setattr(network_command._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(network_command._system, "run_service_action", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(network, "lan_addresses", lambda: ["192.168.0.18"])
    monkeypatch.setattr(network, "pwa_urls", lambda _addresses: [])
    monkeypatch.setattr(network, "refresh_certificate", lambda *_args: None)
    monkeypatch.setattr(network, "update_env", lambda *_args: None)
    monkeypatch.setattr(network_command.platform, "system", lambda: "Linux")
    monkeypatch.setattr(network_command.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        network_command.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    assert network_command.run(SimpleNamespace(network_command="refresh", yes=True), None, ui, None) == 0
