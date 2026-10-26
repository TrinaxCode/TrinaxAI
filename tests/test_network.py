import os
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
    origin_values = set(origins.split(","))
    expected_origins = {
        f"{scheme}://{host}:{port}"
        for host in ("localhost", "Trinax-Host", "192.168.0.18")
        for scheme in ("https", "http")
        for port in (3334, 3335)
    }
    assert origin_values & expected_origins == expected_origins
    assert urls == ["https://192.168.0.18:3334", "https://Trinax-Host.local:3334"]


def test_trust_certificate_prefers_mkcert_root_ca(tmp_path: Path, monkeypatch) -> None:
    ca_root = tmp_path / "mkcert"
    ca_root.mkdir()
    ca_file = ca_root / "rootCA.pem"
    ca_file.write_text("public certificate", encoding="utf-8")
    monkeypatch.setattr(network.shutil, "which", lambda name: "/bin/mkcert" if name == "mkcert" else None)
    monkeypatch.setattr(
        network.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=f"{ca_root}\n", stderr=""),
    )
    assert network.trust_certificate(tmp_path) == (ca_file, "mkcert")


def test_trust_certificate_falls_back_to_leaf_certificate(tmp_path: Path, monkeypatch) -> None:
    certificate = tmp_path / "chat-pwa" / "certs" / "trinaxai-local.crt"
    certificate.parent.mkdir(parents=True)
    certificate.write_text("public certificate", encoding="utf-8")
    monkeypatch.setattr(network.shutil, "which", lambda _name: None)
    assert network.trust_certificate(tmp_path) == (certificate, "self-signed")


def test_update_env_replaces_stale_network_without_touching_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(network.socket, "gethostname", lambda: "trinax")
    env = tmp_path / ".env"
    env.write_text(
        "TRINAXAI_ADMIN_TOKEN=keep-me\n"
        "TRINAXAI_PWA_HOST=127.0.0.1\n"
        "TRINAXAI_CORS_ORIGINS=https://old-router.local:3334\n",
        encoding="utf-8",
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
    assert "TRINAXAI_PWA_HOST=0.0.0.0" in updated
    assert env.stat().st_mode == mode_before


def test_update_env_appends_missing_origin_and_rejects_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("TRINAXAI_ADMIN_TOKEN=keep-me\n", encoding="utf-8")
    network.update_env(tmp_path, ["192.168.0.18"])
    updated = env.read_text(encoding="utf-8")
    assert "TRINAXAI_CORS_ORIGINS=" in updated
    assert "TRINAXAI_PWA_HOST=0.0.0.0" in updated
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
    assert ui.messages.count("https://trinax.local:3334") == 1


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
    if os.name != "nt":
        assert (cert_dir / "localhost.pem").stat().st_mode & 0o777 == 0o600
        assert (cert_dir / "trinaxai-local.crt").stat().st_mode & 0o777 == 0o600


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


def _install_with_host(tmp_path: Path, host_line: str | None) -> Path:
    root = tmp_path / "install"
    root.mkdir(parents=True)
    lines = ["TRINAXAI_ADMIN_TOKEN=secret", "TRINAXAI_CORS_ORIGINS=https://localhost:3334"]
    if host_line is not None:
        lines.append(host_line)
    (root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_lan_access_is_read_from_the_web_apps_bind_address(tmp_path: Path) -> None:
    assert network.lan_access_enabled(_install_with_host(tmp_path / "a", None)) is False  # unset: this computer only
    assert network.lan_access_enabled(_install_with_host(tmp_path / "b", "TRINAXAI_PWA_HOST=127.0.0.1")) is False
    assert network.lan_access_enabled(_install_with_host(tmp_path / "c", 'TRINAXAI_PWA_HOST="localhost"')) is False
    assert network.lan_access_enabled(_install_with_host(tmp_path / "d", "TRINAXAI_PWA_HOST=0.0.0.0")) is True
    assert network.lan_access_enabled(tmp_path / "missing") is False


def test_disable_lan_access_binds_to_this_computer_and_keeps_everything_else(tmp_path: Path) -> None:
    root = _install_with_host(tmp_path, "TRINAXAI_PWA_HOST=0.0.0.0")
    before = (root / ".env").read_text(encoding="utf-8")

    assert network.disable_lan_access(root) is True

    after = (root / ".env").read_text(encoding="utf-8")
    assert after == before.replace("TRINAXAI_PWA_HOST=0.0.0.0", "TRINAXAI_PWA_HOST=127.0.0.1")
    assert network.lan_access_enabled(root) is False
    assert network.disable_lan_access(root) is False  # already limited: nothing rewritten
    with pytest.raises(FileNotFoundError):
        network.disable_lan_access(tmp_path / "missing")


def test_network_status_and_off_command(monkeypatch, tmp_path: Path) -> None:
    root = _install_with_host(tmp_path, "TRINAXAI_PWA_HOST=0.0.0.0")
    monkeypatch.setattr(network_command._system, "project_root", lambda: root)
    monkeypatch.setattr(network_command.network, "lan_addresses", lambda: ["192.168.0.18"])
    actions: list[str] = []
    monkeypatch.setattr(
        network_command._system, "run_service_action", lambda action, _ui, timeout: actions.append(action) or 0
    )

    ui = UI()
    assert network_command.run(SimpleNamespace(network_command=None), None, ui, None) == 0
    assert "Access from other devices: allowed (each device must be paired)" in ui.messages
    assert "Use 'trinaxai network off' to keep TrinaxAI on this computer only." in ui.messages

    ui = UI()
    assert network_command.run(SimpleNamespace(network_command="off", yes=True, no_restart=False), None, ui, None) == 0
    assert "TrinaxAI is now limited to this computer." in ui.messages
    assert actions == ["reload-network"]
    assert network.lan_access_enabled(root) is False

    ui = UI()
    assert network_command.run(SimpleNamespace(network_command=None), None, ui, None) == 0
    assert "Access from other devices: this computer only" in ui.messages
    # Nothing listens on the LAN addresses now, so they are not offered as places to open it.
    assert "https://localhost:3334" in ui.messages
    assert not any("192.168.0.18" in message for message in ui.messages)
    assert "To open TrinaxAI from a phone or another computer, run: trinaxai network refresh" in ui.messages
    ui = UI()
    assert network_command.run(SimpleNamespace(network_command="off", yes=True), None, ui, None) == 0
    assert "Already limited to this computer; nothing to change." in ui.messages
    assert actions == ["reload-network"]  # nothing restarted the second time


def test_network_off_can_be_cancelled_skip_the_restart_or_report_failures(monkeypatch, tmp_path: Path) -> None:
    root = _install_with_host(tmp_path, "TRINAXAI_PWA_HOST=0.0.0.0")
    monkeypatch.setattr(network_command._system, "project_root", lambda: root)
    restarts: list[str] = []
    monkeypatch.setattr(
        network_command._system, "run_service_action", lambda action, _ui, timeout: restarts.append(action) or 1
    )

    declined = UI()
    declined.confirm = lambda *_a, **_k: False  # type: ignore[method-assign]
    assert network_command.run(SimpleNamespace(network_command="off", yes=False), None, declined, None) == 0
    assert "Cancelled." in declined.messages and network.lan_access_enabled(root) is True

    ui = UI()
    args = SimpleNamespace(network_command="off", yes=True, no_restart=True)
    assert network_command.run(args, None, ui, None) == 0
    assert "Restart TrinaxAI to apply it." in ui.messages and restarts == []

    root_again = _install_with_host(tmp_path / "again", "TRINAXAI_PWA_HOST=0.0.0.0")
    monkeypatch.setattr(network_command._system, "project_root", lambda: root_again)
    ui = UI()
    assert network_command.run(SimpleNamespace(network_command="off", yes=True, no_restart=False), None, ui, None) == 1
    assert "Configuration saved. Restart the PWA and RAG services to apply it." in ui.messages

    def broken(_root):
        raise OSError("read-only file system")

    monkeypatch.setattr(network_command.network, "disable_lan_access", broken)
    root_third = _install_with_host(tmp_path / "third", "TRINAXAI_PWA_HOST=0.0.0.0")
    monkeypatch.setattr(network_command._system, "project_root", lambda: root_third)
    ui = UI()
    assert network_command.run(SimpleNamespace(network_command="off", yes=True), None, ui, None) == 1
    assert any(message.startswith("Network change:") for message in ui.messages)


def test_network_off_messages_are_translated() -> None:
    from trinaxai_cli.i18n import translate

    assert translate("Access from other devices: this computer only", "es") == (
        "Acceso desde otros dispositivos: solo este equipo"
    )
    assert translate(
        "To open TrinaxAI from a phone or another computer, run: trinaxai network refresh", "es"
    ).startswith("Para abrir TrinaxAI desde")
    assert translate("TrinaxAI is now limited to this computer.", "es") == "TrinaxAI quedó limitado a este equipo."
    assert translate("Keep TrinaxAI on this computer only?", "es") == "¿Mantener TrinaxAI solo en este equipo?"


def test_env_lines_are_read_the_way_the_service_reads_them(tmp_path: Path) -> None:
    for index, line in enumerate(
        ("  TRINAXAI_PWA_HOST=0.0.0.0", "TRINAXAI_PWA_HOST = 0.0.0.0", "TRINAXAI_PWA_HOST='0.0.0.0'")
    ):
        root = _install_with_host(tmp_path / str(index), line)
        assert network.lan_access_enabled(root) is True, line
        assert network.disable_lan_access(root) is True, line
        assert network.lan_access_enabled(root) is False, line
        assert "0.0.0.0" not in (root / ".env").read_text(encoding="utf-8")


def test_update_env_rewrites_indented_or_spaced_assignments_instead_of_duplicating_them(tmp_path: Path) -> None:
    root = _install_with_host(tmp_path, "  TRINAXAI_PWA_HOST = 127.0.0.1")
    network.update_env(root, ["192.168.1.20"])
    lines = (root / ".env").read_text(encoding="utf-8").splitlines()
    assert sum(1 for raw in lines if raw.split("=", 1)[0].strip() == "TRINAXAI_PWA_HOST") == 1
    assert "TRINAXAI_PWA_HOST=0.0.0.0" in lines
